"""Authenticated uploads and persisted operation/result views. No browser authority."""

import hashlib
import hmac
from collections.abc import Callable, Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Protocol, cast
from urllib.parse import unquote
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import Response
from itsdangerous import BadSignature
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.core.models import Statement
from stmtconv.web.broker import Broker
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import (
    Artifact,
    CanonicalSnapshot,
    Event,
    Job,
    Operation,
    SourceFile,
    User,
    now,
)
from stmtconv.web.repository import Cursors, Json, job_json, replay
from stmtconv.web.schemas import FileOrderCommand, PasswordCommand, PipelineCommand, RevisionCommand
from stmtconv.web.storage import ObjectStore


class Scope(Protocol):
    def __call__(
        self, db: Session, request: Request, *, write: bool = False, owner: bool = False
    ) -> tuple[UUID, User]: ...


def current_job(db: Session, workspace: UUID, job_id: UUID) -> Job:
    job = db.scalar(
        select(Job).where(
            Job.workspace_id == workspace, Job.id == job_id, Job.deletion_state == "active"
        )
    )
    if job is None:
        raise missing()
    return job


def revision(job: Job, expected: int) -> None:
    if job.revision != expected:
        raise WebError(409, "REVISION_CONFLICT", "This job changed. Refresh before trying again.")


def idle(db: Session, job: Job) -> None:
    if db.scalar(
        select(Operation.id).where(
            Operation.workspace_id == job.workspace_id,
            Operation.job_id == job.id,
            Operation.state.in_(["queued", "running", "cancel_requested"]),
        )
    ):
        raise WebError(409, "JOB_BUSY", "Wait for the current operation or cancel it first.")


def operation_json(operation: Operation) -> Json:
    return {
        "id": str(operation.id),
        "job_id": str(operation.job_id),
        "input_revision": operation.input_revision,
        "action": operation.action,
        "state": operation.state,
        "stage": operation.stage,
        "pages_done": operation.completed_pages,
        "pages_total": None,
        "error_code": operation.error_code,
    }


def enqueue(db: Session, config: HostedSettings, job: Job, actor: UUID, action: str) -> Json:
    idle(db, job)
    active = (
        db.scalar(
            select(func.count())
            .select_from(Operation)
            .where(
                Operation.workspace_id == job.workspace_id,
                Operation.state.in_(["queued", "running"]),
            )
        )
        or 0
    )
    recent = (
        db.scalar(
            select(func.count())
            .select_from(Operation)
            .where(
                Operation.workspace_id == job.workspace_id,
                Operation.created_at > now() - timedelta(hours=1),
            )
        )
        or 0
    )
    if active >= config.workspace_operations or recent >= 30:
        raise WebError(429, "TEST_QUOTA", "The workspace's test queue limit has been reached.")
    files = list(
        db.scalars(
            select(SourceFile).where(
                SourceFile.workspace_id == job.workspace_id, SourceFile.job_id == job.id
            )
        )
    )
    if not files:
        raise WebError(409, "FILES_REQUIRED", "Upload a statement first.")
    if action == "extract" and (
        job.status not in {"intake_done", "needs_review", "extracted"}
        or any(f.normalized_id is None for f in files)
    ):
        raise WebError(409, "INTAKE_REQUIRED", "Inspect your documents before conversion.")
    operation = Operation(
        workspace_id=job.workspace_id,
        job_id=job.id,
        actor_id=actor,
        input_revision=job.revision,
        action=action,
        page_limit=config.job_pages,
    )
    db.add(operation)
    db.flush()
    db.add(
        Event(
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=actor,
            action="job." + action + ".queued",
            revision=job.revision,
        )
    )
    return operation_json(operation)


def register_pipeline(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    key: Callable[[Request], str],
    store: ObjectStore,
    broker: Broker,
    cursors: Cursors,
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    @app.get("/api/v1/intake-options")
    def intake_options(request: Request, db: Db) -> Json:
        scoped(db, request)
        from stmtconv.profiles.schema import load_profiles

        return {
            "upload_bytes": config.upload_bytes,
            "job_files": config.job_files,
            "job_pages": config.job_pages,
            "profiles": [{"id": p.id, "name": p.display_name} for p in load_profiles()],
        }

    def page_window(token: str | None, scope: str) -> int:
        if token is None:
            return 0
        try:
            data = cursors.signer.loads(token, max_age=3600)
            if data["scope"] != scope or type(data["offset"]) is not int or data["offset"] < 0:
                raise ValueError
            return int(data["offset"])
        except (BadSignature, KeyError, TypeError, ValueError):
            raise WebError(400, "CURSOR_INVALID", "The page link is invalid or expired.") from None

    def next_token(offset: int, total: int, scope: str) -> str | None:
        return (
            str(cursors.signer.dumps({"scope": scope, "offset": offset}))
            if offset < total
            else None
        )

    def file_json(db: Session, file: SourceFile, job: Job) -> Json:
        artifact = db.get(Artifact, file.artifact_id)
        assert artifact is not None
        return {
            "id": str(file.id),
            "display_name": file.name,
            "bytes": artifact.bytes,
            "sha256": artifact.sha256,
            "pages": len(file.pages),
            "kind": file.kind,
            "password_required": file.password_required,
            "revision": job.revision,
        }

    @app.post("/api/v1/jobs/{job_id}/files")
    async def upload(job_id: UUID, request: Request, db: Db) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)
        try:
            expected = int(request.headers.get("x-expected-revision", ""))
            name = unquote(request.headers.get("x-file-name", ""), errors="strict")
            if (
                not 0 < expected <= 9007199254740991
                or not 1 <= len(name) <= 120
                or any(ord(c) < 32 for c in name)
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            raise WebError(
                422, "INPUT_INVALID", "Supply a filename and current revision."
            ) from None
        if request.headers.get("x-synthetic-confirmed") != "true":
            raise WebError(422, "SYNTHETIC_ONLY", "Confirm that this is a synthetic test document.")
        data = await request.body()
        if not data or len(data) > config.upload_bytes:
            raise WebError(413, "BODY_LIMIT", "The document exceeds the upload limit.")
        kind = (
            "pdf"
            if data.startswith(b"%PDF-")
            else "image"
            if data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"II*\x00", b"MM\x00*"))
            else None
        )
        if kind is None:
            raise WebError(422, "FILE_TYPE", "Use a PDF, JPEG, PNG or TIFF statement.")

        def execute() -> Json:
            revision(job, expected)
            idle(db, job)
            if job.status not in {"created", "intake_done"}:
                raise WebError(409, "UPLOAD_STATE", "Create a new job for different documents.")
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(SourceFile)
                    .where(SourceFile.workspace_id == workspace, SourceFile.job_id == job.id)
                )
                or 0
            )
            used = (
                db.scalar(
                    select(func.coalesce(func.sum(Artifact.bytes), 0)).where(
                        Artifact.workspace_id == workspace, Artifact.state != "removed"
                    )
                )
                or 0
            )
            if count >= config.job_files or used + len(data) > config.workspace_bytes:
                raise WebError(
                    429, "TEST_QUOTA", "The workspace's test storage limit has been reached."
                )
            aid = uuid4()
            artifact = Artifact(
                id=aid,
                workspace_id=workspace,
                job_id=job.id,
                object_key="jobs/" + str(job.id) + "/uploads/" + str(aid),
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                revision=job.revision + 1,
                kind="original",
            )
            store.write(artifact, data)
            db.add(artifact)
            db.flush()
            file = SourceFile(
                workspace_id=workspace,
                job_id=job.id,
                artifact_id=aid,
                name=name,
                kind=kind,
                position=count,
            )
            db.add(file)
            job.revision += 1
            job.status, job.content_digest = "created", None
            # Originals remain valid; all derived pointers are invalidated on changed intake.
            db.execute(
                update(Artifact)
                .where(
                    Artifact.workspace_id == workspace,
                    Artifact.job_id == job.id,
                    Artifact.kind == "original",
                )
                .values(revision=job.revision)
            )
            db.execute(
                update(SourceFile)
                .where(SourceFile.workspace_id == workspace, SourceFile.job_id == job.id)
                .values(normalized_id=None, pages=[], previews={}, password_required=False)
            )
            db.add(
                Event(
                    workspace_id=workspace,
                    job_id=job.id,
                    actor_id=user.id,
                    action="file.uploaded",
                    revision=job.revision,
                )
            )
            db.flush()
            return file_json(db, file, job)

        return replay(
            db,
            workspace,
            user.id,
            "upload:" + str(job.id),
            key(request),
            {
                "name": name,
                "expected_revision": expected,
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            execute,
        )

    @app.get("/api/v1/jobs/{job_id}/files")
    def files(
        job_id: UUID,
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
    ) -> Json:
        workspace, _user = scoped(db, request)
        job = current_job(db, workspace, job_id)
        scope = f"files:{workspace}:{job.id}:{job.revision}"
        offset = page_window(cursor, scope)
        records = list(
            db.scalars(
                select(SourceFile)
                .where(SourceFile.workspace_id == workspace, SourceFile.job_id == job.id)
                .order_by(SourceFile.position)
            )
        )
        return {
            "items": [file_json(db, f, job) for f in records[offset : offset + limit]],
            "next_cursor": next_token(offset + limit, len(records), scope),
        }

    @app.post("/api/v1/jobs/{job_id}/intake", status_code=202)
    def intake(job_id: UUID, body: RevisionCommand, request: Request, db: Db) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)

        def execute() -> Json:
            revision(job, body.expected_revision)
            if job.status not in {"created", "intake_done"}:
                raise WebError(
                    409, "INTAKE_STATE", "Document inspection is unavailable in this state."
                )
            return enqueue(db, config, job, user.id, "intake")

        return replay(
            db,
            workspace,
            user.id,
            "intake:" + str(job.id),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/jobs/{job_id}/operations", status_code=202)
    def convert(job_id: UUID, body: PipelineCommand, request: Request, db: Db) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)

        def execute() -> Json:
            revision(job, body.expected_revision)
            action = "extract"
            if body.action == "retry":
                old = db.scalar(
                    select(Operation).where(
                        Operation.workspace_id == workspace,
                        Operation.job_id == job.id,
                        Operation.id == body.retry_operation_id,
                    )
                )
                if old is None:
                    raise missing()
                if old.state not in {"failed", "cancelled"}:
                    raise WebError(409, "RETRY_STATE", "This operation cannot be retried.")
                action = old.action
            if body.action == "retry":
                assert old is not None
            if (
                body.action == "retry"
                and old is not None
                and action not in {"intake", "extract"}
                and old.input_revision != job.revision
            ):
                raise WebError(
                    409,
                    "REVISION_CONFLICT",
                    "Prepare the operation again for the current revision.",
                )
            result = enqueue(db, config, job, user.id, action)
            if body.action == "retry":
                queued = db.get(Operation, UUID(str(result["id"])))
                assert queued is not None
                assert old is not None
                queued.payload = old.payload
            return result

        return replay(
            db,
            workspace,
            user.id,
            "operation:" + str(job.id),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.get("/api/v1/jobs/{job_id}/operations")
    def operations(job_id: UUID, request: Request, db: Db) -> Json:
        workspace, _user = scoped(db, request)
        job = current_job(db, workspace, job_id)
        records = list(
            db.scalars(
                select(Operation)
                .where(Operation.workspace_id == workspace, Operation.job_id == job.id)
                .order_by(Operation.created_at.desc())
                .limit(30)
            )
        )
        return {"items": [operation_json(o) for o in records], "next_cursor": None}

    @app.get("/api/v1/jobs/{job_id}/operations/{operation_id}")
    def operation(job_id: UUID, operation_id: UUID, request: Request, db: Db) -> Json:
        workspace, _user = scoped(db, request)
        current_job(db, workspace, job_id)
        record = db.scalar(
            select(Operation).where(
                Operation.workspace_id == workspace,
                Operation.job_id == job_id,
                Operation.id == operation_id,
            )
        )
        if record is None:
            raise missing()
        return operation_json(record)

    @app.post("/api/v1/jobs/{job_id}/operations/{operation_id}/cancel", status_code=202)
    def cancel(
        job_id: UUID, operation_id: UUID, body: RevisionCommand, request: Request, db: Db
    ) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)

        def execute() -> Json:
            revision(job, body.expected_revision)
            record = db.scalar(
                select(Operation)
                .where(
                    Operation.workspace_id == workspace,
                    Operation.job_id == job.id,
                    Operation.id == operation_id,
                )
                .with_for_update()
            )
            if record is None:
                raise missing()
            if record.state not in {"queued", "running", "awaiting_input"}:
                raise WebError(409, "CANCEL_STATE", "This operation has already finished.")
            record.state, record.lease_hash, record.lease_until = "cancelled", None, None
            record.error_code = "USER_CANCELLED"
            db.add(
                Event(
                    workspace_id=workspace,
                    job_id=job.id,
                    actor_id=user.id,
                    action="operation.cancelled",
                    revision=job.revision,
                )
            )
            return operation_json(record)

        return replay(
            db,
            workspace,
            user.id,
            "cancel:" + str(operation_id),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/jobs/{job_id}/files/{file_id}/unlock", status_code=202)
    def unlock(
        job_id: UUID, file_id: UUID, body: PasswordCommand, request: Request, db: Db
    ) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)
        file = db.scalar(
            select(SourceFile).where(
                SourceFile.workspace_id == workspace,
                SourceFile.job_id == job.id,
                SourceFile.id == file_id,
            )
        )
        if file is None:
            raise missing()

        def execute() -> Json:
            revision(job, body.expected_revision)
            if not file.password_required:
                raise WebError(409, "PASSWORD_STATE", "This document is not awaiting a password.")
            result = enqueue(db, config, job, user.id, "intake")
            broker.passwords.put(UUID(str(result["id"])), file.id, body.password)
            return result

        fingerprint = hmac.new(
            config.session_key.get_secret_value().encode(), body.password.encode(), hashlib.sha256
        ).hexdigest()
        return replay(
            db,
            workspace,
            user.id,
            "unlock:" + str(file.id),
            key(request),
            {"expected_revision": body.expected_revision, "password_hash": fingerprint},
            execute,
        )

    @app.put("/api/v1/jobs/{job_id}/file-order")
    def file_order(job_id: UUID, body: FileOrderCommand, request: Request, db: Db) -> Json:
        workspace, user = scoped(db, request, write=True)
        job = current_job(db, workspace, job_id)

        def execute() -> Json:
            revision(job, body.expected_revision)
            idle(db, job)
            records = list(
                db.scalars(
                    select(SourceFile).where(
                        SourceFile.workspace_id == workspace, SourceFile.job_id == job.id
                    )
                )
            )
            if (
                job.status not in {"created", "intake_done"}
                or len(set(body.file_ids)) != len(body.file_ids)
                or set(body.file_ids) != {f.id for f in records}
            ):
                raise WebError(
                    422, "FILE_ORDER_INVALID", "Choose every file exactly once before conversion."
                )
            # Two passes avoid collisions in the unique position constraint.
            for f in records:
                f.position += config.job_files + 1
            db.flush()
            for f in records:
                f.position = body.file_ids.index(f.id)
            job.revision += 1
            job.content_digest = None
            db.execute(
                update(Artifact)
                .where(
                    Artifact.workspace_id == workspace,
                    Artifact.job_id == job.id,
                    Artifact.state == "active",
                )
                .values(revision=job.revision)
            )
            db.add(
                Event(
                    workspace_id=workspace,
                    job_id=job.id,
                    actor_id=user.id,
                    action="files.reordered",
                    revision=job.revision,
                )
            )
            return job_json(job)

        return replay(
            db,
            workspace,
            user.id,
            "file-order:" + str(job.id),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    def source(db: Session, workspace: UUID, job_id: UUID, file_id: UUID) -> SourceFile:
        current_job(db, workspace, job_id)
        value = db.scalar(
            select(SourceFile).where(
                SourceFile.workspace_id == workspace,
                SourceFile.job_id == job_id,
                SourceFile.id == file_id,
            )
        )
        if value is None:
            raise missing()
        return value

    @app.get("/api/v1/jobs/{job_id}/files/{file_id}/download")
    def download(job_id: UUID, file_id: UUID, request: Request, db: Db) -> Response:
        workspace, user = scoped(db, request)
        file = source(db, workspace, job_id, file_id)
        data = store.read(db, workspace, user.id, file.artifact_id)
        extension = (
            "pdf"
            if file.kind == "pdf"
            else "png"
            if data.startswith(b"\x89PNG")
            else "jpg"
            if data.startswith(b"\xff\xd8")
            else "tiff"
        )
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="source-document.{extension}"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/api/v1/jobs/{job_id}/files/{file_id}/pages/{page}")
    def preview(job_id: UUID, file_id: UUID, page: int, request: Request, db: Db) -> Response:
        workspace, user = scoped(db, request)
        file = source(db, workspace, job_id, file_id)
        aid = file.previews.get(str(page))
        if aid is None:
            raise missing()
        if (
            db.scalar(
                select(Artifact.id).where(
                    Artifact.id == UUID(aid),
                    Artifact.workspace_id == workspace,
                    Artifact.job_id == job_id,
                    Artifact.kind == "page",
                    Artifact.state == "active",
                )
            )
            is None
        ):
            raise missing()
        return Response(
            store.read(db, workspace, user.id, UUID(aid)),
            media_type="image/png",
            headers={"Cache-Control": "private, no-store"},
        )

    def snapshot(db: Session, job: Job) -> CanonicalSnapshot | None:
        return db.scalar(
            select(CanonicalSnapshot).where(
                CanonicalSnapshot.workspace_id == job.workspace_id,
                CanonicalSnapshot.job_id == job.id,
                CanonicalSnapshot.revision == job.revision,
            )
        )

    @app.get("/api/v1/jobs/{job_id}/statements")
    def statements(job_id: UUID, request: Request, db: Db) -> Json:
        workspace, _user = scoped(db, request)
        job = current_job(db, workspace, job_id)
        snap = snapshot(db, job)
        items: list[Json] = []
        for stored in snap.statements if snap else []:
            domain = Statement.model_validate(stored["domain"])
            items.append(
                {
                    "id": domain.id,
                    "profile_id": stored["profile_id"],
                    "verdict": domain.verdict,
                    "rows": len(domain.transactions),
                    "flags": domain.flags,
                    "checks": domain.checks,
                    "version": stored["version"],
                    "source_checked": bool(
                        cast(Json, job.review_state.get("spotcheck", {})).get("passed")
                    ),
                }
            )
        return {"revision": job.revision, "items": items, "next_cursor": None}

    @app.get("/api/v1/jobs/{job_id}/rows")
    def rows(
        job_id: UUID,
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
    ) -> Json:
        workspace, _user = scoped(db, request)
        job = current_job(db, workspace, job_id)
        scope = f"rows:{workspace}:{job.id}:{job.revision}"
        offset = page_window(cursor, scope)
        snap = snapshot(db, job)
        items: list[Json] = []

        def money(value: Decimal | None) -> str | None:
            return format(value, ".2f") if value is not None else None

        for stored in snap.statements if snap else []:
            domain = Statement.model_validate(stored["domain"])
            for row in domain.transactions:
                items.append(
                    {
                        "id": row.id,
                        "statement_id": domain.id,
                        "sequence": len(items),
                        "date": row.date.isoformat() if row.date else None,
                        "description": row.description,
                        "debit": money(row.debit),
                        "credit": money(row.credit),
                        "balance": money(row.balance),
                        "file_id": row.source_file,
                        "page": row.page,
                        "engine": row.engine,
                        "flags": row.flags,
                        "fixed_by": row.fixed_by,
                        "source_reviewed": row.source_reviewed,
                        "category": row.category,
                    }
                )
        return {
            "revision": job.revision,
            "items": items[offset : offset + limit],
            "next_cursor": next_token(offset + limit, len(items), scope),
        }
