"""Hosted metadata authority. Every resource lookup carries its workspace ID."""

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.orders.metadata import MetadataView
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import Event, Idempotency, Job, Membership, Workspace
from stmtconv.web.schemas import JobOptions

Json = dict[str, object]


@dataclass(frozen=True)
class WorkspaceActor:
    workspace_id: UUID
    user_id: UUID


class ArtifactReader(Protocol):
    def read(self, db: Session, workspace: UUID, actor_id: UUID, artifact_id: UUID) -> bytes: ...


class MetadataRepository(Protocol):
    def get(self, job_id: UUID) -> Json: ...
    def create(self, options: JobOptions) -> Json: ...


def job_json(job: Job) -> Json:
    return {
        "id": str(job.id),
        "name": job.name,
        "status": job.status,
        "revision": job.revision,
        "currency": job.currency,
        "created_at": job.created_at.isoformat(),
        "deletion_state": job.deletion_state,
        "options": job.options,
        "content_digest": job.content_digest,
        "export_revision": None,
        "source_checked": False,
        "ai_source_checked": False,
    }


class HostedMetadata:
    def __init__(self, db: Session, workspace_id: UUID, actor_id: UUID):
        self.db = db
        self.actor = WorkspaceActor(workspace_id, actor_id)

    def get(self, job_id: UUID) -> Json:
        job = self.db.scalar(
            select(Job).where(
                Job.workspace_id == self.actor.workspace_id,
                Job.id == job_id,
                Job.deletion_state == "active",
            )
        )
        if job is None:
            raise missing()
        return job_json(job)

    def describe(self, identifier: UUID) -> MetadataView:
        record = self.get(identifier)
        return MetadataView(
            identifier=str(record["id"]),
            name=str(record["name"]),
            currency=str(record["currency"]),
            status=str(record["status"]),
        )

    def create(self, options: JobOptions) -> Json:
        job = Job(
            workspace_id=self.actor.workspace_id,
            creator_id=self.actor.user_id,
            name=options.name,
            currency=options.currency,
            options=options.model_dump(mode="json"),
        )
        self.db.add(job)
        self.db.flush()
        self.db.add(
            Event(
                workspace_id=self.actor.workspace_id,
                job_id=job.id,
                actor_id=self.actor.user_id,
                action="job.created",
                revision=job.revision,
            )
        )
        return job_json(job)


def membership(
    db: Session, workspace: UUID | None, user: UUID, *, write: bool = False, owner: bool = False
) -> Membership:
    if workspace is None:
        raise missing()
    if write:
        db.execute(select(Workspace.id).where(Workspace.id == workspace).with_for_update()).first()
    result = db.scalar(
        select(Membership)
        .where(
            Membership.workspace_id == workspace,
            Membership.user_id == user,
            Membership.active.is_(True),
        )
        .execution_options(populate_existing=True)
    )
    if result is None:
        raise missing()
    if (owner and result.role != "owner") or (write and result.role == "viewer"):
        raise WebError(403, "ROLE_DENIED", "Your membership does not allow this action.")
    return result


def replay(
    db: Session,
    workspace: UUID,
    actor: UUID,
    action: str,
    key: str,
    payload: Json,
    execute: Callable[[], Json],
) -> Json:
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    old = db.scalar(
        select(Idempotency).where(
            Idempotency.workspace_id == workspace,
            Idempotency.actor_id == actor,
            Idempotency.action == action,
            Idempotency.key == key,
        )
    )
    if old is not None:
        if not hmac.compare_digest(old.fingerprint, fingerprint):
            raise WebError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "That request key was already used for another command.",
            )
        return old.response
    result = execute()
    db.add(
        Idempotency(
            workspace_id=workspace,
            actor_id=actor,
            action=action,
            key=key,
            fingerprint=fingerprint,
            response=result,
        )
    )
    return result


class Cursors:
    def __init__(self, key: str):
        self.signer = URLSafeTimedSerializer(key, salt="scoped-pagination-v1")

    def decode(self, token: str | None, scope: str) -> UUID | None:
        if token is None:
            return None
        try:
            value = self.signer.loads(token, max_age=3600)
            if not isinstance(value, dict) or value.get("scope") != scope:
                raise ValueError
            return UUID(value["after"])
        except (BadSignature, ValueError, KeyError, TypeError):
            raise WebError(400, "CURSOR_INVALID", "The page link is invalid or expired.") from None

    def encode(self, after: UUID, scope: str) -> str:
        return str(self.signer.dumps({"scope": scope, "after": str(after)}))
