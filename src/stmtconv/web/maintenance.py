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
