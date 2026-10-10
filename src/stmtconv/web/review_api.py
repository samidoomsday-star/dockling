"""Scoped revision commands; browser and workbook corrections share the pure core."""

import hashlib
import hmac
from collections.abc import Callable, Iterator
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from stmtconv.catalog import Categories
from stmtconv.config import HostedSettings, load_settings
from stmtconv.errors import StmtconvError
from stmtconv.extract.service import version
from stmtconv.review.commands import ReviewEdit, apply_edits
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import (
    Artifact,
    CanonicalSnapshot,
    CategoryRules,
    Event,
    Job,
    Operation,
    ReviewRevision,
)
from stmtconv.web.pipeline import PipelineTask, digest
from stmtconv.web.pipeline_api import Scope, current_job, enqueue, idle, revision
from stmtconv.web.repository import Json, job_json, replay
from stmtconv.web.schemas import RevisionCommand
from stmtconv.web.storage import ObjectStore
from stmtconv.web.workflow import domains, export_gate, sample_ids, source_basis, source_valid


class EditCommand(RevisionCommand):
    edits: list[ReviewEdit] = Field(min_length=1, max_length=100)


class SourceCommand(RevisionCommand):
    row_ids: list[str] = Field(max_length=10000)
    passed: bool


class ExportOptions(RevisionCommand):
    outputs: list[Literal["excel", "csv", "qb_csv3", "qb_csv4", "xero_csv", "ofx"]] = Field(
        min_length=1, max_length=6
    )
    output_date_format: Literal["ISO", "MM/DD/YYYY", "DD/MM/YYYY"]
    merge: bool
    categorize: bool

    @field_validator("outputs")
    @classmethod
    def unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Choose distinct formats")
        return value


class AccountGroup(RevisionCommand):
    confirmed: bool
    private_group: str = Field(min_length=1, max_length=100, repr=False)


class RuleCommand(RevisionCommand):
    rules: list[dict[str, object]] = Field(max_length=100)

    @field_validator("rules")
    @classmethod
    def safe_rules(cls, value: list[dict[str, object]]) -> list[dict[str, object]]:
        import re

        checked = Categories.model_validate({"rules": value})
        for rule in checked.rules:
            if (
                len(rule.category) > 80
                or len(rule.match) > 20
                or any(ord(c) < 32 for c in rule.category)
            ):
                raise ValueError("Category limits")
            for pattern in rule.match:
                if not pattern or len(pattern) > 120:
                    raise ValueError("Pattern limits")
                if pattern.startswith("regex:"):
                    # Deliberately linear subset: no repetition, groups, backreferences or lookaround.
                    raw = pattern[6:]
                    if not raw or any(c in raw for c in "*+{}()\\"):
                        raise ValueError(
                            "Use literal matching or a simple regex without repetition/groups"
                        )
                    re.compile(raw)
        return [r.model_dump(mode="json") for r in checked.rules]


def snapshot(db: Session, job: Job) -> CanonicalSnapshot:
    row = db.scalar(
        select(CanonicalSnapshot).where(
            CanonicalSnapshot.workspace_id == job.workspace_id,
            CanonicalSnapshot.job_id == job.id,
            CanonicalSnapshot.revision == job.revision,
        )
    )
    if row is None:
        raise WebError(409, "RESULTS_REQUIRED", "Convert statements before reviewing them.")
    return row


def revise(
    db: Session,
    job: Job,
    actor: UUID,
    records: list[dict[str, object]],
    command: Json,
    *,
    preserve_source: bool = False,
) -> None:
    job.revision += 1
    job.content_digest = digest(
        {"sources": job.content_digest, "options": job.options, "statements": records}
    )
    job.export_manifest = {}
    job.delivery_manifest = {}
    state = job.review_state
    job.review_state = (
        {
            k: v
            for k, v in state.items()
            if k in {"spotcheck", "ai_source", "account_group", "rules"}
        }
        if preserve_source
        else {k: v for k, v in state.items() if k == "rules"}
    )
    job.status = "needs_review"
    db.add(
        CanonicalSnapshot(
            workspace_id=job.workspace_id,
            job_id=job.id,
            revision=job.revision,
            digest=job.content_digest,
            statements=records,
        )
    )
    db.add(
        ReviewRevision(
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=actor,
            revision=job.revision,
            command=command,
        )
    )
    db.add(
        Event(
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=actor,
            revision=job.revision,
            action="job.review.changed",
        )
    )
    db.execute(
        update(Artifact)
        .where(
            Artifact.workspace_id == job.workspace_id,
            Artifact.job_id == job.id,
            Artifact.state == "active",
            Artifact.kind.in_(["original", "normalized", "page"]),
        )
        .values(revision=job.revision)
    )


def task_for(job: Job, records: list[dict[str, object]], action: str) -> PipelineTask:
    return PipelineTask(
        id=job.id,
        job_id=job.id,
        workspace_id=job.workspace_id,
        generation=0,
        revision=job.revision,
        action=action,
        files=[],
        options=job.options,
        statements=records,
        review_state=job.review_state,
    )


def register_review(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    key: Callable[[Request], str],
    store: ObjectStore,
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    def edit_job(
        db: Session,
        request: Request,
        jid: UUID,
        command: RevisionCommand,
        action: str,
        execute: Callable[[Job, UUID], Json],
    ) -> Json:
        ws, actor = scoped(db, request, write=True)
        job = current_job(db, ws, jid)

        def run() -> Json:
            revision(job, command.expected_revision)
            idle(db, job)
            return execute(job, actor.id)

        return replay(
            db,
            ws,
            actor.id,
            action + ":" + str(jid),
            key(request),
            command.model_dump(mode="json", exclude_unset=True),
            run,
        )

    @app.patch("/api/v1/jobs/{jid}/review")
    def edit(jid: UUID, command: EditCommand, request: Request, db: Db) -> Json:
        def run(job: Job, actor: UUID) -> Json:
            old = snapshot(db, job).statements
            try:
                changed = apply_edits(domains(old), command.edits, load_settings())
            except StmtconvError as exc:
                raise WebError(422, exc.code, exc.message) from None
            records = [
                {**r, "domain": s.model_dump(mode="json"), "version": version([s])}
                for r, s in zip(old, changed, strict=True)
            ]
            revise(db, job, actor, records, command.model_dump(mode="json", exclude_unset=True))
            return job_json(job)

        return edit_job(db, request, jid, command, "review", run)

    @app.get("/api/v1/jobs/{jid}/checks")
    def checks(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        from stmtconv.core.validate import validate

        statements = [
            validate(s, load_settings().balance_tolerance)
            for s in domains(snapshot(db, job).statements)
        ]
        return {
            "revision": job.revision,
            "items": [
                {"id": s.id, "verdict": s.verdict, "checks": s.checks, "flags": s.flags}
                for s in statements
            ],
            "source_checked": source_valid(job.review_state, statements, str(jid)),
            "ai_source_checked": source_valid(job.review_state, statements, str(jid), True),
        }

    @app.get("/api/v1/jobs/{jid}/spotcheck")
    @app.get("/api/v1/jobs/{jid}/ai-source")
    def source_check(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        statements = domains(snapshot(db, job).statements)
        ai = request.url.path.endswith("ai-source")
        ids = (
            [s.id + ":" + t.id for s in statements for t in s.transactions if t.engine == "ai"]
            if ai
            else sample_ids(str(jid), statements)
        )
        rows = [
            {
                "id": s.id + ":" + t.id,
                "statement_id": s.id,
                "row_id": t.id,
                "file_id": t.source_file,
                "page": t.page,
                "date": t.date.isoformat() if t.date else None,
                "description": t.description,
                "debit": format(t.debit, ".2f") if t.debit is not None else None,
                "credit": format(t.credit, ".2f") if t.credit is not None else None,
                "balance": format(t.balance, ".2f") if t.balance is not None else None,
            }
            for s in statements
            for t in s.transactions
            if s.id + ":" + t.id in ids
        ]
        return {
            "revision": job.revision,
            "row_ids": ids,
            "items": rows,
            "passed": source_valid(job.review_state, statements, str(jid), ai),
        }

    @app.post("/api/v1/jobs/{jid}/spotcheck")
    @app.post("/api/v1/jobs/{jid}/ai-source")
    def confirm(jid: UUID, command: SourceCommand, request: Request, db: Db) -> Json:
        ai = request.url.path.endswith("ai-source")

        def run(job: Job, actor: UUID) -> Json:
            statements = domains(snapshot(db, job).statements)
            ids = (
                [s.id + ":" + t.id for s in statements for t in s.transactions if t.engine == "ai"]
                if ai
                else sample_ids(str(jid), statements)
            )
            if command.row_ids != ids:
                raise WebError(
                    409,
                    "SOURCE_SAMPLE_CHANGED",
                    "Compare every required row in the current sample.",
                )
            db.add(
                ReviewRevision(
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    actor_id=actor,
                    revision=job.revision,
                    command={
                        "action": "ai-source" if ai else "spotcheck",
                        "row_ids": ids,
                        "passed": command.passed,
                    },
                )
            )
            field = "ai_source" if ai else "spotcheck"
            job.review_state = {
                **job.review_state,
                field: {
                    "basis": source_basis(statements),
                    "revision": job.revision,
                    "row_ids": ids,
                    "passed": command.passed,
                    "actor_id": str(actor),
                },
            }
            if job.status in {"needs_review", "reviewed"}:
                from stmtconv.core.validate import validate

                ready = all(
                    validate(s, load_settings().balance_tolerance).verdict
                    not in {"NEEDS_REVIEW", "UNVERIFIABLE"}
                    for s in statements
                )
                ready = (
                    ready
                    and source_valid(job.review_state, statements, str(jid))
                    and source_valid(job.review_state, statements, str(jid), True)
                )
                job.status = "reviewed" if ready else "needs_review"
            db.add(
                Event(
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    actor_id=actor,
                    revision=job.revision,
                    action="job." + field + ".recorded",
                )
            )
            return job_json(job)

        return edit_job(db, request, jid, command, "ai-source" if ai else "spotcheck", run)

    @app.post("/api/v1/jobs/{jid}/recheck")
    def recheck(jid: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        return edit_job(
            db, request, jid, command, "recheck", lambda _job, _actor: checks(jid, request, db)
        )

    @app.get("/api/v1/jobs/{jid}/review-history")
    def history(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        current_job(db, ws, jid)
        records = db.scalars(
            select(ReviewRevision)
            .where(ReviewRevision.workspace_id == ws, ReviewRevision.job_id == jid)
            .order_by(ReviewRevision.revision.desc())
            .limit(100)
        )
        return {
            "items": [
                {
                    "revision": r.revision,
                    "actor_id": str(r.actor_id),
                    "at": r.at.isoformat(),
                    "command": r.command,
                }
                for r in records
            ],
            "next_cursor": None,
        }

    @app.post("/api/v1/jobs/{jid}/merge-preview")
    def merge_preview(jid: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        def run(job: Job, _actor: UUID) -> Json:
            from stmtconv.core.merge import merge

            statements = domains(snapshot(db, job).statements)
            group = job.review_state.get("account_group")
            combination = merge(
                statements, load_settings().balance_tolerance, str(group) if group else None
            )
            return {
                "revision": job.revision,
                "issues": [i.model_dump(mode="json") for i in combination.issues],
                "statements": len(statements),
                "rows": sum(len(s.transactions) for s in statements),
                "allowed": not combination.issues,
            }

        return edit_job(db, request, jid, command, "merge-preview", run)

    @app.post("/api/v1/jobs/{jid}/categories/preview")
    def category_preview(jid: UUID, command: RuleCommand, request: Request, db: Db) -> Json:
        def run(job: Job, _actor: UUID) -> Json:
            from stmtconv.core.categorize import Rule, categorize

            statements = domains(snapshot(db, job).statements)
            categorized = [
                categorize(
                    s,
                    [
                        Rule(r.category, r.match, r.direction)
                        for r in Categories.model_validate({"rules": command.rules}).rules
                    ],
                )
                for s in statements
            ]
            return {
                "revision": job.revision,
                "items": [
                    {"statement_id": s.id, "row_id": t.id, "category": t.category}
                    for s in categorized
                    for t in s.transactions
                ][:100],
                "limit": 100,
            }

        return edit_job(db, request, jid, command, "category-preview", run)

    @app.patch("/api/v1/jobs/{jid}/output-options")
    def options(jid: UUID, command: ExportOptions, request: Request, db: Db) -> Json:
        def run(job: Job, actor: UUID) -> Json:
            records = snapshot(db, job).statements
            job.options = {**job.options, **command.model_dump(exclude={"expected_revision"})}
            revise(db, job, actor, records, {"action": "output-options"}, preserve_source=True)
            return job_json(job)

        return edit_job(db, request, jid, command, "output-options", run)

    @app.post("/api/v1/jobs/{jid}/account-group")
    def account(jid: UUID, command: AccountGroup, request: Request, db: Db) -> Json:
        def run(job: Job, actor: UUID) -> Json:
            if not command.confirmed:
                raise WebError(
                    422, "ACCOUNT_CONFIRMATION", "Confirm the statements belong to one account."
                )
            records = snapshot(db, job).statements
            group = hmac.new(
                config.session_key.get_secret_value().encode(),
                f"account:{job.workspace_id}:{command.private_group}".encode(),
                hashlib.sha256,
            ).hexdigest()
            revise(db, job, actor, records, {"action": "account-group"}, preserve_source=True)
            job.review_state = {**job.review_state, "account_group": group}
            return job_json(job)

        return edit_job(db, request, jid, command, "account-group", run)

    @app.get("/api/v1/categories")
    def categories(request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        rules = db.get(CategoryRules, ws)
        return {"version": rules.version if rules else 1, "rules": rules.rules if rules else []}

    @app.put("/api/v1/categories")
    def category_write(command: RuleCommand, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True)

        def run() -> Json:
            rules = db.get(CategoryRules, ws)
            current = rules.version if rules else 1
            if current != command.expected_revision:
                raise WebError(409, "REVISION_CONFLICT", "Category rules changed. Refresh first.")
            jobs = list(
                db.scalars(
                    select(Job).where(Job.workspace_id == ws, Job.deletion_state == "active")
                )
            )
            for job in jobs:
                if not job.options.get("categorize") or not job.content_digest:
                    continue
                idle(db, job)
                revise(
                    db,
                    job,
                    actor.id,
                    snapshot(db, job).statements,
                    {"action": "workspace-categories"},
                    preserve_source=True,
                )
            if rules:
                rules.rules, rules.version = command.rules, current + 1
            else:
                rules = CategoryRules(workspace_id=ws, rules=command.rules, version=current + 1)
                db.add(rules)
            return {"version": rules.version, "rules": rules.rules}

        return replay(
            db, ws, actor.id, "categories", key(request), command.model_dump(mode="json"), run
        )

    @app.get("/api/v1/jobs/{jid}/categories")
    def job_rules(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        return {"version": job.revision, "rules": job.review_state.get("rules", [])}

    @app.put("/api/v1/jobs/{jid}/categories")
    def overrides(jid: UUID, command: RuleCommand, request: Request, db: Db) -> Json:
        def run(job: Job, actor: UUID) -> Json:
            revise(
                db,
                job,
                actor,
                snapshot(db, job).statements,
                {"action": "job-categories"},
                preserve_source=True,
            )
            job.review_state = {**job.review_state, "rules": command.rules}
            return job_json(job)

        return edit_job(db, request, jid, command, "categories", run)

    @app.get("/api/v1/jobs/{jid}/review-workbooks")
    @app.get("/api/v1/jobs/{jid}/exports")
    @app.get("/api/v1/jobs/{jid}/delivery")
    def outputs(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        name = request.url.path.rsplit("/", 1)[-1]
        manifest = (
            job.review_state.get("workbooks", {})
            if name == "review-workbooks"
            else job.export_manifest
            if name == "exports"
            else job.delivery_manifest
        )
        return {
            "revision": job.revision,
            "items": cast(Json, manifest).get("items", [])
            if cast(Json, manifest).get("revision") == job.revision
            else [],
        }

    @app.post("/api/v1/jobs/{jid}/review-workbooks", status_code=202)
    @app.post("/api/v1/jobs/{jid}/exports", status_code=202)
    @app.post("/api/v1/jobs/{jid}/delivery", status_code=202)
    def prepare(jid: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        name = request.url.path.rsplit("/", 1)[-1]
        action = {
            "review-workbooks": "review_workbook",
            "exports": "export",
            "delivery": "delivery",
        }[name]

        def run(job: Job, actor: UUID) -> Json:
            records = snapshot(db, job).statements
            if action in {"export", "delivery"}:
                try:
                    export_gate(task_for(job, records, action), load_settings())
                except StmtconvError as exc:
                    raise WebError(409, exc.code, exc.message) from None
            payload: Json = {}
            if action == "export":
                rules = db.get(CategoryRules, job.workspace_id)
                payload = {
                    "rules": [
                        *cast(list[Json], job.review_state.get("rules", [])),
                        *(rules.rules if rules else []),
                    ],
                    "created_at": job.created_at.strftime("%Y%m%d%H%M%S"),
                }
            elif action == "delivery":
                if job.export_manifest.get(
                    "revision"
                ) != job.revision or not job.export_manifest.get("items"):
                    raise WebError(
                        409,
                        "EXPORT_REQUIRED",
                        "Generate current exports before preparing delivery.",
                    )
                payload = {"exports": job.export_manifest["items"]}
                for item in cast(list[Json], payload["exports"]):
                    store.read(db, job.workspace_id, actor, UUID(str(item["id"])))
            response = enqueue(db, config, job, actor, action)
            operation = db.get(Operation, UUID(str(response["id"])))
            assert operation is not None
            operation.payload = payload
            return response

        return edit_job(db, request, jid, command, action, run)

    @app.get("/api/v1/jobs/{jid}/artifacts/{aid}/download")
    def download(jid: UUID, aid: UUID, request: Request, db: Db) -> Response:
        ws, actor = scoped(db, request)
        job = current_job(db, ws, jid)
        manifests = [
            job.export_manifest,
            job.delivery_manifest,
            job.review_state.get("workbooks", {}),
        ]
        item = next(
            (
                i
                for m in manifests
                if isinstance(m, dict) and m.get("revision") == job.revision
                for i in cast(list[Json], m.get("items", []))
                if i.get("id") == str(aid)
            ),
            None,
        )
        if item is None:
            raise missing()
        content = store.read(db, ws, actor.id, aid)
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise WebError(503, "ARTIFACT_INTEGRITY", "This download could not be verified.")
        return Response(
            content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="' + str(item["name"]) + '"'},
        )

    @app.post("/api/v1/jobs/{jid}/review-workbooks/{aid}/apply", status_code=202)
    async def workbook_apply(jid: UUID, aid: UUID, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True)
        job = current_job(db, ws, jid)
        try:
            expected = int(request.headers.get("x-expected-revision", ""))
        except ValueError:
            raise WebError(422, "INPUT_INVALID", "The current revision is required.") from None
        data = await request.body()
        if not data or len(data) > config.upload_bytes:
            raise WebError(413, "BODY_LIMIT", "The workbook is too large.")

        def run() -> Json:
            revision(job, expected)
            idle(db, job)
            manifest = cast(Json, job.review_state.get("workbooks", {}))
            item = next(
                (i for i in cast(list[Json], manifest.get("items", [])) if i.get("id") == str(aid)),
                None,
            )
            if item is None or manifest.get("revision") != job.revision:
                raise WebError(409, "REVIEW_STALE", "Download a current review workbook first.")
            from sqlalchemy import func

            used = (
                db.scalar(
                    select(func.coalesce(func.sum(Artifact.bytes), 0)).where(
                        Artifact.workspace_id == ws, Artifact.state != "removed"
                    )
                )
                or 0
            )
            if used + len(data) > config.workspace_bytes:
                raise WebError(
                    429, "TEST_QUOTA", "The workspace's test storage limit has been reached."
                )
            from uuid import uuid4

            upload_id = uuid4()
            response = enqueue(db, config, job, actor.id, "review_apply")
            operation = db.get(Operation, UUID(str(response["id"])))
            assert operation is not None
            artifact = Artifact(
                id=upload_id,
                workspace_id=ws,
                job_id=jid,
                revision=job.revision,
                kind="review_upload",
                object_key="pipeline/" + str(operation.id) + "/0/" + str(upload_id),
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                state="active",
                operation_id=operation.id,
                generation=0,
            )
            db.add(artifact)
            db.flush()
            store.write(artifact, data)
            operation.payload = {
                "upload_id": str(upload_id),
                "statement_id": item["statement_id"],
                "binding": item["binding"],
            }
            return response

        return replay(
            db,
            ws,
            actor.id,
            "review-apply:" + str(jid),
            key(request),
            {
                "revision": expected,
                "workbook": str(aid),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            run,
        )
