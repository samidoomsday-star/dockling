"""Restore quarantine and scoped tombstone replay. Neither resumes paid work nor certifies deletion."""

from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from stmtconv.web.models import (
    AiAttempt,
    AiConsent,
    AiRun,
    Artifact,
    Invitation,
    Job,
    Operation,
    WebSession,
)
from stmtconv.web.storage import ObjectStore


def quarantine(db: Session) -> None:
    """Before starting a restored API, invalidate old authority and persisted work leases.

    Uncertain AI reservations stay held. A terminal state is not a memory-erasure
    receipt; gateway cleanup_done is preserved, never forged by a database edit.
    """
    db.execute(update(WebSession).values(revoked=True))
    db.execute(update(Invitation).where(Invitation.status == "pending").values(status="revoked"))
    db.execute(update(AiConsent).values(granted=False, private={}))
    db.execute(
        update(AiRun)
        .where(AiRun.state.in_(["queued", "running"]))
        .values(state="cancelled", error_code="AI_RECOVERY_REVIEW")
    )
    db.execute(update(AiAttempt).where(AiAttempt.state == "sending").values(state="uncertain"))
    db.execute(
        update(Operation)
        .where(Operation.state.in_(["queued", "running", "cancel_requested"]))
        .values(state="cancelled", lease_hash=None, lease_until=None, error_code="RESTORE_REVIEW")
    )


def replay_removals(
    db: Session, store: ObjectStore, authoritative: dict[tuple[UUID, UUID], str]
) -> dict[str, int]:
    """Remove restored live copies for newer, independently supplied deletion tombstones.

    The caller must supply a verified current deletion journal; a stale backup alone
    cannot invent it. Jobs stay fenced as pending, with no inherited certificate.
    Only their recorded objects and verified pipeline/upload prefixes are touched.
    """
    result = {"jobs_fenced": 0, "objects_removed": 0}
    if len(authoritative) > 10000:
        raise ValueError("Deletion journal exceeds the local restore bound")
    for (workspace, identifier), state in authoritative.items():
        if state not in {"pending", "partial", "removed"}:
            raise ValueError("Unverified deletion state")
        job = db.scalar(
            select(Job).where(Job.workspace_id == workspace, Job.id == identifier).with_for_update()
        )
        if job is None or job.deletion_state == "removed":
            continue
        job.deletion_state = "pending"
        job.export_manifest, job.delivery_manifest = {}, {}
        job.removal = {
            "restore_fence": True,
            "authoritative_live_state": state,
            "certificate": None,
        }
        artifacts = list(
            db.scalars(
                select(Artifact).where(
                    Artifact.workspace_id == workspace, Artifact.job_id == identifier
                )
            )
        )
        keys = {artifact.object_key for artifact in artifacts}
        prefixes = ["uploads/" + str(identifier) + "/"]
        prefixes.extend(
            "pipeline/" + str(op) + "/"
            for op in db.scalars(
                select(Operation.id).where(
                    Operation.workspace_id == workspace, Operation.job_id == identifier
                )
            )
        )
        for prefix in prefixes:
            for page in store.client.get_paginator("list_objects_v2").paginate(
                Bucket=store.bucket, Prefix=prefix
            ):
                keys.update(item["Key"] for item in page.get("Contents", []))
                if len(keys) > 10000:
                    raise ValueError("Restored deletion inventory exceeds its bound")
        for key in keys:
            store.client.delete_object(Bucket=store.bucket, Key=key)
            try:
                store.client.head_object(Bucket=store.bucket, Key=key)
            except ClientError as error:
                if str(error.response["Error"]["Code"]) not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            else:
                raise ValueError("Restored object removal is unverified")
            result["objects_removed"] += 1
        for artifact in artifacts:
            artifact.state = "removed"
        result["jobs_fenced"] += 1
    return result
