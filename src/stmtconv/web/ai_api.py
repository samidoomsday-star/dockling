"""Owner consent and conservative, durable job-level generation reservations."""

from collections.abc import Callable, Iterator
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from pydantic import Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stmtconv.ai.providers import Effort, Provider, choose
from stmtconv.config import HostedSettings
from stmtconv.errors import StmtconvError
from stmtconv.web.ai_core import minimized, pages
from stmtconv.web.connections import get_connection
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import AiAttempt, AiConsent, AiRun, Connection, Event, Job
from stmtconv.web.owner_config import processing_settings
from stmtconv.web.pipeline import digest
from stmtconv.web.pipeline_api import Scope, current_job, idle, revision
from stmtconv.web.repository import Json, membership, replay
from stmtconv.web.review_api import snapshot
from stmtconv.web.schemas import RevisionCommand


class ConsentCommand(RevisionCommand):
    expected_consent_version: int = Field(ge=0)
    granted: bool
    connection_id: UUID | None = Field(default=None, strict=False)
    consent_note: str = Field(default="", max_length=500, repr=False)
    mask_names: list[str] = Field(default_factory=list, max_length=40, repr=False)
    page_cap: int = Field(default=5, ge=1, le=100)
    request_cap: int = Field(default=5, ge=1, le=100)

    @field_validator("mask_names")
    @classmethod
    def names(cls, values: list[str]) -> list[str]:
        if any(not n.strip() or len(n) > 100 or any(ord(c) < 32 for c in n) for n in values):
            raise ValueError("Use visible names, at most 100 characters each")
        return list(dict.fromkeys(n.strip() for n in values))


class AiRequest(RevisionCommand):
    consent_version: int = Field(ge=1)
    page_keys: list[str] = Field(min_length=1, max_length=5)
    acknowledge_prior_uncertainty: bool = False

    @field_validator("page_keys")
    @classmethod
    def distinct(cls, value: list[str]) -> list[str]:
        import re

        if len(value) != len(set(value)) or any(
            not re.fullmatch(r"[a-f0-9]{64}", k) for k in value
        ):
            raise ValueError("Choose distinct current page keys")
        return value


def binding(job: Job, connection: Connection, config: HostedSettings) -> str:
    return digest(
        {
            "revision": job.revision,
            "content": job.content_digest,
            "options": job.options,
            "runtime_config": job.runtime_config,
            "connection": str(connection.id),
            "version": connection.version,
            "model": connection.selected_model,
            "effort": connection.effort,
            "terms": connection.terms_version,
            "config": connection.config,
            "gateway": "masked-cells-v1",
            "tolerance": str(processing_settings(job.runtime_config).balance_tolerance),
            "platform_limits": [config.ai_page_cap, config.ai_request_cap, config.ai_pages_per_run],
        }
    )


def consent_for(db: Session, job: Job) -> AiConsent | None:
    return db.scalar(
        select(AiConsent).where(
            AiConsent.workspace_id == job.workspace_id, AiConsent.job_id == job.id
        )
    )


def checked(
    db: Session, job: Job, config: HostedSettings, run: AiRun | None = None
) -> tuple[AiConsent, Connection]:
    consent = consent_for(db, job)
    if not consent or not consent.granted or consent.connection_id is None:
        raise WebError(
            409, "AI_CONSENT_REQUIRED", "A workspace owner must grant consent for this job."
        )
    membership(db, job.workspace_id, consent.actor_id, owner=True)
    connection = get_connection(db, job.workspace_id, consent.connection_id, active=True)
    if (
        not connection.terms_version
        or connection.config.get("requires_key", True)
        and not connection.ciphertext
    ):
        raise WebError(
            409, "AI_GATE_CLOSED", "Save suitable provider terms and any required key first."
        )
    if (
        consent.binding != binding(job, connection, config)
        or run
        and (
            run.input_revision != job.revision
            or run.consent_version != consent.version
            or run.binding != consent.binding
        )
    ):
        raise WebError(
            409,
            "AI_CONSENT_CHANGED",
            "The content or model settings changed. Record consent again; existing usage stays counted.",
        )
    configured = Provider.model_validate(
        {"name": "hosted", **connection.config, "models": connection.models}
    )
    try:
        choose(configured, connection.selected_model or "", cast(Effort, connection.effort))
    except StmtconvError:
        raise WebError(
            409,
            "AI_MODEL_UNSUPPORTED",
            "Choose a currently supported model and effort before renewing consent.",
        ) from None
    return consent, connection


def run_json(run: AiRun) -> Json:
    return {
        "id": str(run.id),
        "job_id": str(run.job_id),
        "input_revision": run.input_revision,
        "state": run.state,
        "error_code": run.error_code,
        "pages_reserved": len(run.page_keys),
        "requests_reserved": len(run.page_keys),
        "cleanup_done": run.cleanup_done,
    }


def usage(db: Session, job: Job) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(func.jsonb_array_length(AiRun.page_keys)), 0)).where(
                AiRun.workspace_id == job.workspace_id, AiRun.job_id == job.id
            )
        )
        or 0
    )


def register_ai(
    app: FastAPI,
    config: HostedSettings,
    db_provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    key: Callable[[Request], str],
) -> None:
    Db = Annotated[Session, Depends(db_provider, scope="function")]

    @app.get("/api/v1/jobs/{jid}/ai")
    def status(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        consent = consent_for(db, job)
        valid = False
        code: str | None = "AI_CONSENT_REQUIRED"
        if consent:
            try:
                checked(db, job, config)
                valid, code = True, None
            except Exception:
                code = "AI_CONSENT_CHANGED" if consent.granted else "AI_CONSENT_REQUIRED"
        from stmtconv.web.models import CanonicalSnapshot

        record = db.scalar(
            select(CanonicalSnapshot).where(
                CanonicalSnapshot.workspace_id == ws,
                CanonicalSnapshot.job_id == jid,
                CanonicalSnapshot.revision == job.revision,
            )
        )
        inventory = pages(record.statements) if record else {}
        return {
            "revision": job.revision,
            "consent": {
                "version": consent.version,
                "valid": valid,
                "granted": consent.granted,
                "connection_id": str(consent.connection_id) if consent.connection_id else None,
                "page_cap": consent.page_cap,
                "request_cap": consent.request_cap,
            }
            if consent
            else None,
            "gate_code": code,
            "pages_used": usage(db, job),
            "requests_used": usage(db, job),
            "platform_page_cap": config.ai_page_cap,
            "platform_request_cap": config.ai_request_cap,
            "pages_per_run": config.ai_pages_per_run,
            "pages": [
                {
                    **{k: v for k, v in p.items() if k != "row_ids"},
                    "rows": len(cast(list[str], p["row_ids"])),
                }
                for p in inventory.values()
            ],
            "runs": [
                run_json(r)
                for r in db.scalars(
                    select(AiRun)
                    .where(AiRun.workspace_id == ws, AiRun.job_id == jid)
                    .order_by(AiRun.created_at.desc(), AiRun.id)
                    .limit(20)
                )
            ],
        }

    @app.post("/api/v1/jobs/{jid}/consent")
    def consent(jid: UUID, command: ConsentCommand, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True, owner=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            record = consent_for(db, job)
            if (record.version if record else 0) != command.expected_consent_version:
                raise WebError(
                    409, "CONSENT_CONFLICT", "The consent changed. Refresh before trying again."
                )
            if command.page_cap > config.ai_page_cap or command.request_cap > config.ai_request_cap:
                raise WebError(422, "AI_CAP_LIMIT", "Choose limits within the platform maximum.")
            connection = None
            signature = ""
            if command.granted:
                idle(db, job)
                snapshot(db, job)
                if not command.connection_id or not command.consent_note.strip():
                    raise WebError(
                        422,
                        "AI_CONSENT_NOTE",
                        "Choose a connection and record the client's permission.",
                    )
                connection = get_connection(db, ws, command.connection_id, active=True)
                configured = Provider.model_validate(
                    {"name": "hosted", **connection.config, "models": connection.models}
                )
                try:
                    choose(
                        configured, connection.selected_model or "", cast(Effort, connection.effort)
                    )
                except Exception:
                    raise WebError(
                        422,
                        "AI_MODEL_UNSUPPORTED",
                        "Choose a currently supported model and effort first.",
                    ) from None
                if (
                    not connection.terms_version
                    or connection.config.get("requires_key", True)
                    and not connection.ciphertext
                ):
                    raise WebError(
                        409,
                        "AI_GATE_CLOSED",
                        "Confirm suitable provider terms and save any required key.",
                    )
                signature = binding(job, connection, config)
            if record is None:
                record = AiConsent(job_id=job.id, workspace_id=ws, actor_id=actor.id)
                db.add(record)
                record.version = 0
            record.version += 1
            record.actor_id, record.granted = actor.id, command.granted
            record.connection_id = connection.id if connection else None
            record.binding, record.page_cap, record.request_cap = (
                signature,
                command.page_cap,
                command.request_cap,
            )
            record.private = (
                {"note": command.consent_note, "names": command.mask_names}
                if command.granted
                else {}
            )
            if not command.granted:
                for run in db.scalars(
                    select(AiRun).where(
                        AiRun.workspace_id == ws,
                        AiRun.job_id == jid,
                        AiRun.state.in_(["queued", "running"]),
                    )
                ):
                    run.state, run.error_code = "cancelled", "AI_CONSENT_REVOKED"
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=actor.id,
                    action="ai.consent.changed",
                    revision=job.revision,
                )
            )
            db.flush()
            return status(jid, request, db)

        return replay(
            db,
            ws,
            actor.id,
            "ai.consent:" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/jobs/{jid}/ai/requests", status_code=202)
    def reserve(jid: UUID, command: AiRequest, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            idle(db, job)
            consent, _ = checked(db, job, config)
            if command.consent_version != consent.version:
                raise WebError(409, "CONSENT_CONFLICT", "Use the current consent version.")
            if len(command.page_keys) > config.ai_pages_per_run:
                raise WebError(422, "AI_RUN_LIMIT", "Select fewer pages for this request.")
            used = usage(db, job)
            if used + len(command.page_keys) > min(
                consent.page_cap, consent.request_cap, config.ai_page_cap, config.ai_request_cap
            ):
                raise WebError(
                    429,
                    "AI_BUDGET",
                    "This request exceeds the job's reserved page/request allowance.",
                )
            records = snapshot(db, job).statements
            for page in command.page_keys:
                try:
                    minimized(records, page, cast(list[str], consent.private.get("names", [])))
                except Exception:
                    raise WebError(
                        422,
                        "AI_TABLE_LIMIT",
                        "Choose current pages with safely isolated transaction cells.",
                    ) from None
            uncertain = db.scalar(
                select(AiAttempt.id)
                .where(
                    AiAttempt.workspace_id == ws,
                    AiAttempt.job_id == jid,
                    AiAttempt.page_key.in_(command.page_keys),
                    AiAttempt.state.in_(["sending", "uncertain"]),
                )
                .limit(1)
            )
            if uncertain and not command.acknowledge_prior_uncertainty:
                raise WebError(
                    409,
                    "AI_RETRY_ACK",
                    "The earlier request may have completed or been charged. Confirm that risk before a new request.",
                )
            active = (
                db.scalar(
                    select(func.count())
                    .select_from(AiRun)
                    .where(AiRun.workspace_id == ws, AiRun.state.in_(["queued", "running"]))
                )
                or 0
            )
            if active >= config.workspace_operations:
                raise WebError(429, "AI_QUEUE_LIMIT", "The workspace AI queue is full.")
            from datetime import timedelta

            from stmtconv.web.models import now

            recent = (
                db.scalar(
                    select(func.count())
                    .select_from(AiRun)
                    .where(AiRun.workspace_id == ws, AiRun.created_at > now() - timedelta(hours=1))
                )
                or 0
            )
            if recent >= 30:
                raise WebError(
                    429, "AI_RATE_LIMIT", "The workspace has reached its hourly AI request limit."
                )
            run = AiRun(
                id=uuid4(),
                workspace_id=ws,
                job_id=jid,
                actor_id=actor.id,
                input_revision=job.revision,
                consent_version=consent.version,
                binding=consent.binding,
                page_keys=command.page_keys,
            )
            db.add(run)
            db.flush()
            for page in command.page_keys:
                db.add(AiAttempt(run_id=run.id, workspace_id=ws, job_id=jid, page_key=page))
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=actor.id,
                    action="ai.request.reserved",
                    revision=job.revision,
                )
            )
            db.flush()
            return run_json(run)

        return replay(
            db,
            ws,
            actor.id,
            "ai.reserve:" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/jobs/{jid}/ai/requests/{rid}/cancel")
    def cancel(jid: UUID, rid: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            run = db.scalar(
                select(AiRun).where(AiRun.id == rid, AiRun.workspace_id == ws, AiRun.job_id == jid)
            )
            if run is None:
                raise missing()
            if run.state in {"queued", "running"}:
                run.state, run.error_code = "cancelled", "AI_CANCELLED"
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=actor.id,
                    action="ai.request.cancelled",
                    revision=job.revision,
                )
            )
            return run_json(run)

        return replay(
            db,
            ws,
            actor.id,
            "ai.cancel:" + str(rid) + ":" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )
