"""Verified hosted live-data cleanup. Partial failure never produces a certificate."""

import hashlib
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stmtconv.web.models import (
    Artifact,
    CanonicalSnapshot,
    Event,
    Idempotency,
    Job,
    Membership,
    Operation,
    ReviewRevision,
    ScratchAttempt,
    SourceFile,
    Workspace,
    now,
)
from stmtconv.web.storage import ObjectStore


def object_inventory(store: ObjectStore, prefixes: list[str]) -> list[dict[str, object]]:
    items: dict[tuple[str, str], dict[str, object]] = {}
    for prefix in prefixes:
        args: dict[str, object] = {"Bucket": store.bucket, "Prefix": prefix, "MaxKeys": 1000}
        while True:
            page = store.client.list_object_versions(**args)
            for item in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
                key = item["Key"]
                if not prefix.endswith("/") and key != prefix:
                    continue
                items[key, item["VersionId"]] = {"Key": key, "VersionId": item["VersionId"]}
                if len(items) > 50000:
                    raise ValueError("Live removal inventory limit")
            if not page.get("IsTruncated"):
                break
            args["KeyMarker"] = page["NextKeyMarker"]
            if page.get("NextVersionIdMarker"):
                args["VersionIdMarker"] = page["NextVersionIdMarker"]
    return list(items.values())


def remove_live(
    db: Session, job: Job, operation: Operation, store: ObjectStore
) -> dict[str, object]:
    db.scalar(select(Workspace).where(Workspace.id == job.workspace_id).with_for_update())
    db.refresh(job, with_for_update=True)
    db.refresh(operation, with_for_update=True)
    member = db.scalar(
        select(Membership).where(
            Membership.workspace_id == job.workspace_id,
            Membership.user_id == operation.actor_id,
            Membership.active.is_(True),
            Membership.role == "owner",
        )
    )
    if (
        member is None
        or job.deletion_state not in {"pending", "partial"}
        or job.revision != operation.input_revision
        or operation.state != "running"
        or operation.lease_until is None
        or operation.lease_until <= now()
    ):
        raise ValueError("Removal fence")
    if db.scalar(
        select(ScratchAttempt.operation_id)
        .where(
            ScratchAttempt.workspace_id == job.workspace_id,
            ScratchAttempt.job_id == job.id,
            ScratchAttempt.completed.is_(False),
        )
        .limit(1)
    ):
        raise ValueError("Scratch cleanup not acknowledged")
    from stmtconv.web.models import AiAttempt, AiConsent, AiRun, ProfileEvidence, SupportGrant

    if db.scalar(
        select(AiRun.id)
        .where(
            AiRun.workspace_id == job.workspace_id,
            AiRun.job_id == job.id,
            AiRun.cleanup_done.is_(False),
        )
        .limit(1)
    ):
        raise ValueError("AI memory cleanup has not been acknowledged")
    artifacts = list(
        db.scalars(
            select(Artifact).where(
                Artifact.workspace_id == job.workspace_id, Artifact.job_id == job.id
            )
        )
    )
    ops = list(
        db.scalars(
            select(Operation).where(
                Operation.workspace_id == job.workspace_id, Operation.job_id == job.id
            )
        )
    )
    prefixes = (
        [a.object_key for a in artifacts]
        + ["pipeline/" + str(o.id) + "/" for o in ops]
        + ["jobs/" + str(job.id) + "/"]
    )
    inventory = object_inventory(store, prefixes)
    previous = job.removal.get("inventory_hashes", [])
    hashes = sorted(
        set(
            cast(list[str], previous)
            + [
                hashlib.sha256((str(i["Key"]) + ":" + str(i["VersionId"])).encode()).hexdigest()
                for i in inventory
            ]
        )
    )
    job.removal = {**job.removal, "inventory_hashes": hashes}
    # Keep transaction committed on failure so progress/partial status is durable.
    try:
        for item in inventory:
            store.client.delete_object(Bucket=store.bucket, **item)
        if object_inventory(store, prefixes):
            raise ValueError("Object versions remain")
    except Exception:
        job.deletion_state = "partial"
        operation.state, operation.error_code = "failed", "REMOVAL_PARTIAL"
        operation.lease_hash, operation.lease_until = None, None
        return {"removed": False, "deletion_state": "partial"}
    ws, jid = job.workspace_id, job.id
    for model in (
        ProfileEvidence,
        SupportGrant,
        AiAttempt,
        AiRun,
        AiConsent,
        SourceFile,
        CanonicalSnapshot,
        ReviewRevision,
        Artifact,
    ):
        db.execute(delete(model).where(model.workspace_id == ws, model.job_id == jid))
    # Every job-specific idempotency action ends with the job UUID. Old recorded
    # commands may contain names or row data and cannot survive live removal.
    db.execute(
        delete(Idempotency).where(
            Idempotency.workspace_id == ws,
            (
                Idempotency.action.endswith(str(jid))
                | (Idempotency.response["id"].astext == str(jid))
                | (Idempotency.response["job_id"].astext == str(jid))
            ),
        )
    )
    for old in ops:
        old.payload = {}
    job.name, job.currency, job.options = "Removed job", "XXX", {}
    job.content_digest, job.review_state, job.export_manifest, job.delivery_manifest = (
        None,
        {},
        {},
        {},
    )
    job.runtime_config = {}
    job.status, job.deletion_state = "closed", "removed"
    certificate = {
        "job_id": str(jid),
        "scope": "verified_live_data_removal",
        "completed_at": now().isoformat(),
        "object_versions_removed": len(hashes),
        "inventory_digest": hashlib.sha256("".join(hashes).encode()).hexdigest(),
        "worker_scratch_verified": True,
        "backup_expiry_verified": False,
    }
    job.removal = {"certificate": certificate}
    operation.state, operation.stage, operation.error_code = "succeeded", "finished", None
    operation.lease_hash, operation.lease_until = None, None
    db.add(
        Event(
            workspace_id=ws,
            job_id=jid,
            actor_id=operation.actor_id,
            revision=job.revision,
            action="job.live_data.removed",
        )
    )
    db.flush()
    for model in (
        ProfileEvidence,
        SupportGrant,
        AiAttempt,
        AiRun,
        AiConsent,
        SourceFile,
        CanonicalSnapshot,
        ReviewRevision,
        Artifact,
    ):
        if db.scalar(
            select(model.job_id).where(model.workspace_id == ws, model.job_id == jid).limit(1)
        ):
            raise ValueError("Private database inventory remains")
    return {"removed": True, "certificate": certificate}
