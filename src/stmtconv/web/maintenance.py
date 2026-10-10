"""Conservative, bounded cleanup of abandoned pipeline objects; never active source data."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from stmtconv.web.database import PostgresUnitOfWork
from stmtconv.web.models import Artifact, Operation, SourceFile, Workspace, now
from stmtconv.web.storage import ObjectStore


def reap(
    store: ObjectStore,
    uow: PostgresUnitOfWork,
    cursors: dict[str, str] | None = None,
    *,
    min_age: timedelta = timedelta(hours=1),
) -> tuple[dict[str, int], dict[str, str]]:
    """One page per owned prefix per call; repeat cursors to cover large inventories.

    The grace period exceeds bounded storage/SQL transactions. Inventory lookup is
    repeated at deletion; live attempts and every original/current source are kept.
    Storage failure stops the pass; it is never reported as successful deletion.
    """
    cutoff = now() - min_age
    counts = {"examined": 0, "deleted": 0}
    next_cursors: dict[str, str] = {}
    for prefix in ("uploads/", "pipeline/"):
        args = {"Bucket": store.bucket, "Prefix": prefix, "MaxKeys": 1000}
        if cursors and prefix in cursors:
            args["ContinuationToken"] = cursors[prefix]
        page = store.client.list_objects_v2(**args)
        if page.get("IsTruncated"):
            next_cursors[prefix] = page["NextContinuationToken"]
        for item in page.get("Contents", []):
            counts["examined"] += 1
            key = item["Key"]
            parts = key.split("/")
            try:
                # Only opaque keys minted by this pipeline; no arbitrary bucket purge.
                if prefix == "uploads/" and len(parts) == 3:
                    UUID(parts[1])
                    UUID(parts[2])
                elif prefix == "pipeline/" and len(parts) == 4:
                    UUID(parts[1])
                    UUID(parts[3])
                    assert int(parts[2]) > 0
                else:
                    continue
            except (ValueError, AssertionError):
                continue
            if item["LastModified"] >= cutoff:
                continue
            with uow.transaction() as db:
                artifact = db.scalar(select(Artifact).where(Artifact.object_key == key))
                if artifact is not None:
                    db.scalar(
                        select(Workspace)
                        .where(Workspace.id == artifact.workspace_id)
                        .with_for_update()
                    )
                    db.refresh(artifact)
                    if (
                        artifact.state == "active"
                        or artifact.kind == "original"
                        or artifact.created_at >= cutoff
                    ):
                        continue
                    if any(
                        f.artifact_id == artifact.id
                        or f.normalized_id == artifact.id
                        or str(artifact.id) in f.previews.values()
                        for f in db.scalars(
                            select(SourceFile).where(
                                SourceFile.workspace_id == artifact.workspace_id,
                                SourceFile.job_id == artifact.job_id,
                            )
                        )
                    ):
                        continue
                    op = db.scalar(
                        select(Operation)
                        .where(Operation.id == artifact.operation_id)
                        .with_for_update()
                    )
                    if (
                        op
                        and op.state in {"queued", "running", "cancel_requested"}
                        and op.lease_generation == artifact.generation
                    ):
                        continue
                store.client.delete_object(Bucket=store.bucket, Key=key)
                if artifact:
                    artifact.state = "removed"
                counts["deleted"] += 1
    return counts, next_cursors


def schedule_retention(
    uow: PostgresUnitOfWork, days: int, *, apply: bool = False
) -> dict[str, int]:
    """Explicit local owner maintenance, not a published hosted retention guarantee."""
    from stmtconv.web.models import Event, Job, Membership

    if not 1 <= days <= 365:
        raise ValueError("Choose a retention interval from 1 to 365 days")
    cutoff = now() - timedelta(days=days)
    counts = {"eligible": 0, "queued": 0}
    with uow.transaction() as db:
        jobs = list(
            db.scalars(
                select(Job)
                .where(Job.status == "delivered", Job.deletion_state == "active")
                .order_by(Job.workspace_id, Job.id)
            )
        )
        for candidate in jobs:
            db.scalar(
                select(Workspace).where(Workspace.id == candidate.workspace_id).with_for_update()
            )
            db.refresh(candidate, with_for_update=True)
            if candidate.deletion_state != "active" or candidate.status != "delivered":
                continue
            delivered = db.scalar(
                select(Event.at)
                .where(
                    Event.workspace_id == candidate.workspace_id,
                    Event.job_id == candidate.id,
                    Event.action == "job.delivery.completed",
                )
                .order_by(Event.at.desc())
                .limit(1)
            )
            if not delivered or delivered >= cutoff:
                continue
            counts["eligible"] += 1
            if not apply:
                continue
            if db.scalar(
                select(Operation.id)
                .where(
                    Operation.workspace_id == candidate.workspace_id,
                    Operation.job_id == candidate.id,
                    Operation.state.in_(["queued", "running", "cancel_requested"]),
                )
                .limit(1)
            ):
                continue
            owner = db.scalar(
                select(Membership)
                .where(
                    Membership.workspace_id == candidate.workspace_id,
                    Membership.active.is_(True),
                    Membership.role == "owner",
                )
                .order_by(Membership.id)
                .limit(1)
            )
            if owner is None:
                continue
            candidate.revision += 1
            candidate.deletion_state = "pending"
            candidate.export_manifest, candidate.delivery_manifest = {}, {}
            candidate.removal = {"requested_at": now().isoformat(), "retention_days": days}
            db.add(
                Operation(
                    workspace_id=candidate.workspace_id,
                    job_id=candidate.id,
                    actor_id=owner.user_id,
                    input_revision=candidate.revision,
                    action="close",
                )
            )
            db.add(
                Event(
                    workspace_id=candidate.workspace_id,
                    job_id=candidate.id,
                    actor_id=None,
                    revision=candidate.revision,
                    action="job.retention.requested",
                )
            )
            counts["queued"] += 1
    return counts
