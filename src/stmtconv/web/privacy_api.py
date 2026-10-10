"""Owner-confirmed live removal. Access stops before durable cleanup starts."""

from collections.abc import Callable, Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import Event, Job, Operation
from stmtconv.web.pipeline_api import Scope, operation_json, revision
from stmtconv.web.repository import Json, replay
from stmtconv.web.schemas import RevisionCommand


class RemovalCommand(RevisionCommand):
    confirm_removal: bool
    abandon_unfinished: bool = False
    reason: str = Field(default="", max_length=250)


def register_privacy(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    key: Callable[[Request], str],
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    @app.get("/api/v1/jobs/{jid}/privacy")
    def policy(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = db.scalar(select(Job).where(Job.workspace_id == ws, Job.id == jid))
        if job is None:
            raise missing()
        operation = db.scalar(
            select(Operation)
            .where(
                Operation.workspace_id == ws, Operation.job_id == jid, Operation.action == "close"
            )
            .order_by(Operation.created_at.desc())
            .limit(1)
        )
        return {
            "job_id": str(jid),
            "revision": job.revision,
            "deletion_state": job.deletion_state,
            "certificate": job.removal.get("certificate"),
            "operation": operation_json(operation) if operation else None,
            "retention_days": None,
            "backup_expiry_days": None,
            "scope": "verified_live_data_removal",
            "automatic_retention": False,
        }

    @app.post("/api/v1/jobs/{jid}/close", status_code=202)
    def close(jid: UUID, command: RemovalCommand, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True, owner=True)
        job = db.scalar(select(Job).where(Job.workspace_id == ws, Job.id == jid).with_for_update())
        if job is None:
            raise missing()

        def run() -> Json:
            revision(job, command.expected_revision)
            if not command.confirm_removal:
                raise WebError(
                    422, "REMOVAL_CONFIRMATION", "Confirm permanent live data removal first."
                )
            if job.deletion_state == "removed":
                return {"deletion_state": "removed", "certificate": job.removal.get("certificate")}
            if (
                job.status != "delivered"
                and job.deletion_state == "active"
                and not command.abandon_unfinished
            ):
                raise WebError(
                    409,
                    "ABANDON_CONFIRMATION",
                    "Confirm abandonment before removing an unfinished job.",
                )
            active = list(
                db.scalars(
                    select(Operation)
                    .where(
                        Operation.workspace_id == ws,
                        Operation.job_id == jid,
                        Operation.state.in_(["queued", "running", "cancel_requested"]),
                    )
                    .with_for_update()
                )
            )
            existing = next((o for o in active if o.action == "close"), None)
            if existing:
                return operation_json(existing)
            for o in active:
                o.state, o.lease_hash, o.lease_until = "cancelled", None, None
                o.error_code = "INPUT_REVOKED"
            from stmtconv.web.models import AiConsent, AiRun

            for ai in db.scalars(
                select(AiRun).where(
                    AiRun.workspace_id == ws,
                    AiRun.job_id == jid,
                    AiRun.state.in_(["queued", "running"]),
                )
            ):
                ai.state, ai.error_code = "cancelled", "AI_INPUT_REVOKED"
            consent = db.get(AiConsent, jid)
            if consent:
                consent.granted, consent.private = False, {}
            # End active operations before the partial unique index sees close.
            db.flush()
            job.revision += 1
            job.deletion_state = "pending"
            job.export_manifest, job.delivery_manifest = {}, {}
            job.removal = {
                "requested_at": __import__("stmtconv.web.models", fromlist=["now"])
                .now()
                .isoformat(),
                "abandoned": command.abandon_unfinished,
            }
            operation = Operation(
                workspace_id=ws,
                job_id=jid,
                actor_id=actor.id,
                input_revision=job.revision,
                action="close",
                page_limit=config.job_pages,
            )
            db.add(operation)
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=actor.id,
                    action="job.removal.requested",
                    revision=job.revision,
                )
            )
            db.flush()
            return operation_json(operation)

        return replay(
            db,
            ws,
            actor.id,
            "close:" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            run,
        )
