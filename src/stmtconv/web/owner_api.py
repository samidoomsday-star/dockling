"""Owner preferences, validated global versions, isolated utilities and named-job support."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Annotated, Literal, Protocol, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from pydantic import Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.auth import is_admin
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import (
    AdminSpace,
    Artifact,
    ConfigHead,
    ConfigVersion,
    Event,
    Job,
    Membership,
    Operation,
    ProfileEvidence,
    ServiceReport,
    SourceFile,
    SupportGrant,
    User,
    WebSession,
    Workspace,
    WorkspacePreferences,
    now,
)
from stmtconv.web.owner_config import active, baseline, runtime_snapshot, validate
from stmtconv.web.pipeline import digest
from stmtconv.web.pipeline_api import Scope, current_job, idle, operation_json, revision
from stmtconv.web.repository import Json, replay
from stmtconv.web.review_api import snapshot
from stmtconv.web.schemas import Command, JobOptions, RevisionCommand
from stmtconv.web.storage import ObjectStore

DEFAULTS: Json = {
    "currency": "USD",
    "date_order": "auto",
    "output_date_format": "ISO",
    "outputs": ["excel", "csv"],
    "retention_days": None,
}


class Actor(Protocol):
    def __call__(
        self, db: Session, request: Request, *, write: bool = False
    ) -> tuple[WebSession, User]: ...


class Preferences(Command):
    expected_version: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date_order: Literal["auto", "DMY", "MDY", "YMD"]
    output_date_format: Literal["ISO", "MM/DD/YYYY", "DD/MM/YYYY"]
    outputs: list[Literal["excel", "csv", "qb_csv3", "qb_csv4", "xero_csv", "ofx"]] = Field(
        min_length=1, max_length=6
    )

    @field_validator("outputs")
    @classmethod
    def distinct(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Choose distinct output formats")
        return value


class ConfigCommand(Command):
    expected_version: int = Field(ge=0)
    data: dict[str, object]
    reason: str = Field(min_length=1, max_length=250)
    activate: bool = False
    synthetic_review_confirmed: bool = False
    evidence_id: UUID | None = Field(default=None, strict=False)


class ScaffoldCommand(RevisionCommand):
    file_id: UUID = Field(strict=False)


class ProfileTest(Command):
    profile: dict[str, object]


class GrantCommand(RevisionCommand):
    actor_id: UUID = Field(strict=False)
    scopes: list[Literal["results", "source", "profile_scaffold"]] = Field(
        min_length=1, max_length=3
    )
    minutes: int = Field(default=30, ge=1, le=60)
    reason: str = Field(min_length=1, max_length=250)


class GrantRevoke(RevisionCommand):
    expected_version: int = Field(ge=1)


def preferences(db: Session, workspace: UUID) -> Json:
    record = db.get(WorkspacePreferences, workspace)
    return {"version": record.version, **record.data} if record else {"version": 0, **DEFAULTS}


def admin_space(db: Session, user: User) -> UUID:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
        {"scope": "diagnostics:" + str(user.id)},
    )
    space = db.get(AdminSpace, user.id)
    if space is None:
        workspace = Workspace(name="Private synthetic diagnostics")
        db.add(workspace)
        db.flush()
        db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
        space = AdminSpace(actor_id=user.id, workspace_id=workspace.id)
        db.add(space)
        db.flush()
    return space.workspace_id


def grant_json(grant: SupportGrant) -> Json:
    return {
        "id": str(grant.id),
        "job_id": str(grant.job_id),
        "actor_id": str(grant.actor_id),
        "version": grant.version,
        "revision": grant.revision,
        "scopes": grant.scopes,
        "expires_at": grant.expires_at.isoformat(),
        "revoked": grant.revoked,
    }


def health_data(db: Session, store: ObjectStore) -> Json:
    db.execute(text("SELECT 1"))
    report = db.get(ServiceReport, "worker")
    healthy = bool(report and report.heartbeat_at > now() - timedelta(seconds=60))
    return {
        "database": "healthy",
        "storage": "healthy" if store.healthy() else "unhealthy",
        "worker": "healthy" if healthy else ("unhealthy" if report else "unknown"),
        "models": "verified" if report else "unknown",
        "worker_seen_at": report.heartbeat_at.isoformat() if report else None,
        "models_verified_at": report.models_verified_at.isoformat() if report else None,
        "model_manifest_digest": report.model_digest if report else None,
    }


def register_owner(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    actor: Actor,
    key: Callable[[Request], str],
    store: ObjectStore,
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    def admin(db: Session, request: Request, write: bool = False) -> User:
        session, user = actor(db, request, write=write)
        if not is_admin(config, session, user):
            raise WebError(
                403,
                "ADMIN_MFA_REQUIRED",
                "Administrator access requires a fresh verified second-factor sign-in.",
            )
        return user

    @app.put("/api/v1/settings")
    def save_preferences(command: Preferences, request: Request, db: Db) -> Json:
        ws, user = scoped(db, request, write=True, owner=True)

        def execute() -> Json:
            record = db.get(WorkspacePreferences, ws)
            if (record.version if record else 0) != command.expected_version:
                raise WebError(
                    409, "CONFIG_CONFLICT", "The preferences changed. Refresh before saving."
                )
            JobOptions(name="Defaults", **command.model_dump(exclude={"expected_version"}))
            if record is None:
                record = WorkspacePreferences(workspace_id=ws, version=0, data={})
                db.add(record)
            record.version += 1
            record.data = {
                **command.model_dump(mode="json", exclude={"expected_version"}),
                "retention_days": None,
            }
            db.add(
                Event(
                    workspace_id=ws,
                    actor_id=user.id,
                    action="preferences.updated",
                    revision=record.version,
                )
            )
            db.flush()
            return preferences(db, ws)

        return replay(
            db, ws, user.id, "preferences", key(request), command.model_dump(mode="json"), execute
        )

    @app.get("/api/v1/admin/config/{section}")
    def config_read(section: str, request: Request, db: Db) -> Json:
        admin(db, request)
        base = baseline(section)
        head = db.get(ConfigHead, section)
        versions = list(
            db.scalars(
                select(ConfigVersion)
                .where(ConfigVersion.section == section)
                .order_by(ConfigVersion.version.desc())
                .limit(20)
            )
        )
        return {
            "section": section,
            "version": head.version if head else 0,
            "active_version": head.active_version if head else None,
            "data": versions[0].data if versions else base,
            "active_data": active(db, section),
            "history": [
                {"version": v.version, "data": v.data, "at": v.at.isoformat(), "reason": v.reason}
                for v in versions
            ],
            "visibility": "internal configuration; pricing is not a published customer offer",
        }

    @app.put("/api/v1/admin/config/{section}")
    def config_write(section: str, command: ConfigCommand, request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        ws = admin_space(db, user)

        def execute() -> Json:
            try:
                data = validate(section, command.data)
            except Exception:
                raise WebError(
                    422,
                    "CONFIG_INVALID",
                    "The section did not pass its supported schema and limits.",
                ) from None
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                {"scope": "config:" + section},
            )
            head = db.get(ConfigHead, section)
            if (head.version if head else 0) != command.expected_version:
                raise WebError(
                    409, "CONFIG_CONFLICT", "This section changed. Refresh before saving."
                )
            if command.activate and section.startswith("profile_"):
                evidence = (
                    db.get(ProfileEvidence, command.evidence_id) if command.evidence_id else None
                )
                if (
                    not command.synthetic_review_confirmed
                    or not evidence
                    or not evidence.passed
                    or evidence.profile_digest != digest(data)
                ):
                    raise WebError(
                        409,
                        "PROFILE_TEST_REQUIRED",
                        "Run the exact draft against the synthetic profile test and confirm no customer fingerprints are being published.",
                    )
                if ws != evidence.workspace_id:
                    raise missing()
            if head is None:
                head = ConfigHead(section=section, version=0)
                db.add(head)
                db.flush()
            head.version += 1
            if command.activate:
                head.active_version = head.version
            db.add(
                ConfigVersion(
                    section=section,
                    version=head.version,
                    actor_id=user.id,
                    data=data,
                    reason=command.reason,
                )
            )
            db.add(
                Event(
                    workspace_id=ws,
                    actor_id=user.id,
                    action="config.activated" if command.activate else "config.draft.saved",
                    revision=head.version,
                )
            )
            db.flush()
            return config_read(section, request, db)

        return replay(
            db,
            ws,
            user.id,
            "config:" + section,
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    def utility(db: Session, job: Job, user: User, action: str, payload: Json) -> Json:
        idle(db, job)
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
        active_count = (
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
        if recent >= 30 or active_count >= config.workspace_operations:
            raise WebError(429, "TEST_QUOTA", "The utility queue is full.")
        operation = Operation(
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=user.id,
            input_revision=job.revision,
            action=action,
            payload=payload,
            page_limit=config.job_pages,
        )
        db.add(operation)
        db.add(
            Event(
                workspace_id=job.workspace_id,
                job_id=job.id,
                actor_id=user.id,
                action="utility." + action + ".queued",
                revision=job.revision,
            )
        )
        db.flush()
        return operation_json(operation)

    @app.post("/api/v1/jobs/{jid}/profile-scaffolds", status_code=202)
    def scaffold(jid: UUID, command: ScaffoldCommand, request: Request, db: Db) -> Json:
        ws, user = scoped(db, request, write=True, owner=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            source = db.scalar(
                select(SourceFile).where(
                    SourceFile.workspace_id == ws,
                    SourceFile.job_id == jid,
                    SourceFile.id == command.file_id,
                )
            )
            if not source or not source.normalized_id:
                raise missing()
            return utility(
                db, job, user, "profile_scaffold", {"source_artifact": str(source.normalized_id)}
            )

        return replay(
            db,
            ws,
            user.id,
            "profile-scaffold:" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/admin/selftest", status_code=202)
    def selftest(request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        ws = admin_space(db, user)

        def execute() -> Json:
            options = JobOptions(
                name="Synthetic selftest", currency="USD", date_order="auto", outputs=["csv"]
            )
            job = Job(
                workspace_id=ws,
                creator_id=user.id,
                name=options.name,
                currency="USD",
                options=options.model_dump(mode="json"),
                runtime_config=runtime_snapshot(db),
            )
            db.add(job)
            db.flush()
            return utility(db, job, user, "selftest", {})

        return replay(db, ws, user.id, "selftest", key(request), {}, execute)

    @app.post("/api/v1/admin/profiles/{identifier}/tests", status_code=202)
    def profile_test(identifier: str, command: ProfileTest, request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        ws = admin_space(db, user)

        def execute() -> Json:
            try:
                data = validate("profile_" + identifier, command.profile)
            except Exception:
                raise WebError(
                    422,
                    "PROFILE_INVALID",
                    "The profile did not pass its supported schema and limits.",
                ) from None
            options = JobOptions(
                name="Synthetic profile test", currency="USD", date_order="auto", outputs=["csv"]
            )
            job = Job(
                workspace_id=ws,
                creator_id=user.id,
                name=options.name,
                currency="USD",
                options=options.model_dump(mode="json"),
                runtime_config=runtime_snapshot(db),
            )
            db.add(job)
            db.flush()
            return utility(
                db, job, user, "profile_test", {"profile": data, "profile_digest": digest(data)}
            )

        return replay(
            db,
            ws,
            user.id,
            "profile-test:" + identifier,
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.get("/api/v1/jobs/{jid}/utilities")
    def utilities(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        job = current_job(db, ws, jid)
        manifests = cast(Json, job.review_state.get("utilities", {}))
        return {
            "revision": job.revision,
            "items": [
                i
                for m in manifests.values()
                if isinstance(m, dict) and m.get("revision") == job.revision
                for i in cast(list[Json], m.get("items", []))
            ],
        }

    @app.get("/api/v1/admin/diagnostics/{jid}")
    def diagnostic(jid: UUID, request: Request, db: Db) -> Json:
        user = admin(db, request)
        space = db.get(AdminSpace, user.id)
        if not space:
            raise missing()
        job = current_job(db, space.workspace_id, jid)
        operation = db.scalar(
            select(Operation)
            .where(Operation.workspace_id == space.workspace_id, Operation.job_id == jid)
            .order_by(Operation.created_at.desc())
            .limit(1)
        )
        manifests = cast(Json, job.review_state.get("utilities", {}))
        evidence = list(
            db.scalars(
                select(ProfileEvidence).where(
                    ProfileEvidence.workspace_id == space.workspace_id,
                    ProfileEvidence.job_id == jid,
                )
            )
        )
        return {
            "job_id": str(jid),
            "revision": job.revision,
            "operation": operation_json(operation) if operation else None,
            "reports": [
                i
                for m in manifests.values()
                if isinstance(m, dict)
                for i in cast(list[Json], m.get("items", []))
            ],
            "evidence": [
                {
                    "artifact_id": str(e.artifact_id),
                    "profile_digest": e.profile_digest,
                    "passed": e.passed,
                }
                for e in evidence
            ],
        }

    def attachment(db: Session, job: Job, aid: UUID) -> Response:
        artifact = db.scalar(
            select(Artifact).where(
                Artifact.workspace_id == job.workspace_id,
                Artifact.job_id == job.id,
                Artifact.id == aid,
                Artifact.revision == job.revision,
                Artifact.state == "active",
                Artifact.kind.in_(["profile_scaffold", "diagnostic"]),
            )
        )
        if not artifact:
            raise missing()
        manifests = cast(Json, job.review_state.get("utilities", {}))
        if not any(
            str(aid) == str(i.get("id"))
            for m in manifests.values()
            if isinstance(m, dict)
            for i in cast(list[Json], m.get("items", []))
        ):
            raise missing()
        return Response(
            store.verified(artifact),
            media_type="application/json",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": 'attachment; filename="private-report.json"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/v1/jobs/{jid}/utilities/{aid}/download")
    def download(jid: UUID, aid: UUID, request: Request, db: Db) -> Response:
        ws, user = scoped(db, request, owner=True)
        job = current_job(db, ws, jid)
        db.add(
            Event(
                workspace_id=ws,
                job_id=jid,
                actor_id=user.id,
                action="utility.report.read",
                revision=job.revision,
            )
        )
        return attachment(db, job, aid)

    @app.get("/api/v1/admin/diagnostics/{jid}/{aid}/download")
    def diagnostic_download(jid: UUID, aid: UUID, request: Request, db: Db) -> Response:
        user = admin(db, request)
        space = db.get(AdminSpace, user.id)
        if not space:
            raise missing()
        job = current_job(db, space.workspace_id, jid)
        db.add(
            Event(
                workspace_id=job.workspace_id,
                job_id=jid,
                actor_id=user.id,
                action="diagnostic.report.read",
                revision=job.revision,
            )
        )
        return attachment(db, job, aid)

    @app.get("/api/v1/support-operators")
    def operators(request: Request, db: Db) -> Json:
        scoped(db, request, owner=True)
        return {
            "items": [
                {"id": str(u.id), "display_name": "Support operator " + str(u.id)[:8]}
                for u in db.scalars(
                    select(User)
                    .where(
                        User.issuer == config.oidc_issuer, User.subject.in_(config.admin_subjects)
                    )
                    .limit(20)
                )
            ]
        }

    @app.get("/api/v1/jobs/{jid}/support-grants")
    def grants(jid: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request, owner=True)
        current_job(db, ws, jid)
        return {
            "items": [
                grant_json(g)
                for g in db.scalars(
                    select(SupportGrant)
                    .where(SupportGrant.workspace_id == ws, SupportGrant.job_id == jid)
                    .order_by(SupportGrant.expires_at.desc())
                    .limit(20)
                )
            ]
        }

    @app.post("/api/v1/jobs/{jid}/support-grants", status_code=201)
    def grant(jid: UUID, command: GrantCommand, request: Request, db: Db) -> Json:
        ws, user = scoped(db, request, write=True, owner=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            assigned = db.get(User, command.actor_id)
            if (
                not assigned
                or assigned.issuer != config.oidc_issuer
                or assigned.subject not in config.admin_subjects
            ):
                raise missing()
            if len(command.scopes) != len(set(command.scopes)):
                raise WebError(422, "GRANT_SCOPE", "Choose distinct support permissions.")
            live = (
                db.scalar(
                    select(func.count())
                    .select_from(SupportGrant)
                    .where(
                        SupportGrant.workspace_id == ws,
                        SupportGrant.job_id == jid,
                        SupportGrant.revoked.is_(False),
                        SupportGrant.expires_at > now(),
                    )
                )
                or 0
            )
            if live >= 5:
                raise WebError(429, "GRANT_LIMIT", "Revoke an old grant before creating another.")
            record = SupportGrant(
                workspace_id=ws,
                job_id=jid,
                actor_id=assigned.id,
                owner_id=user.id,
                revision=job.revision,
                scopes=command.scopes,
                expires_at=now() + timedelta(minutes=command.minutes),
                reason=command.reason,
            )
            db.add(record)
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=user.id,
                    action="support.granted",
                    revision=job.revision,
                )
            )
            db.flush()
            return grant_json(record)

        return replay(
            db,
            ws,
            user.id,
            "support.grant:" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/jobs/{jid}/support-grants/{gid}/revoke")
    def revoke(jid: UUID, gid: UUID, command: GrantRevoke, request: Request, db: Db) -> Json:
        ws, user = scoped(db, request, write=True, owner=True)
        job = current_job(db, ws, jid)

        def execute() -> Json:
            revision(job, command.expected_revision)
            record = db.scalar(
                select(SupportGrant).where(
                    SupportGrant.workspace_id == ws,
                    SupportGrant.job_id == jid,
                    SupportGrant.id == gid,
                )
            )
            if not record:
                raise missing()
            if record.version != command.expected_version:
                raise WebError(409, "GRANT_CONFLICT", "This support grant changed.")
            record.revoked = True
            record.version += 1
            db.add(
                Event(
                    workspace_id=ws,
                    job_id=jid,
                    actor_id=user.id,
                    action="support.revoked",
                    revision=job.revision,
                )
            )
            return grant_json(record)

        return replay(
            db,
            ws,
            user.id,
            "support.revoke:" + str(gid) + ":" + str(jid),
            key(request),
            command.model_dump(mode="json"),
            execute,
        )

    @app.get("/api/v1/admin/support-grants")
    def assigned(request: Request, db: Db) -> Json:
        user = admin(db, request)
        return {
            "items": [
                grant_json(g)
                for g in db.scalars(
                    select(SupportGrant)
                    .where(
                        SupportGrant.actor_id == user.id,
                        SupportGrant.revoked.is_(False),
                        SupportGrant.expires_at > now(),
                    )
                    .limit(20)
                )
            ]
        }

    def support(db: Session, request: Request, gid: UUID, scope: str) -> tuple[User, Job]:
        user = admin(db, request)
        grant = db.get(SupportGrant, gid)
        if not grant or grant.actor_id != user.id:
            raise missing()
        db.scalar(select(Workspace).where(Workspace.id == grant.workspace_id).with_for_update())
        db.refresh(grant)
        job = current_job(db, grant.workspace_id, grant.job_id)
        owner = db.scalar(
            select(Membership.id).where(
                Membership.workspace_id == grant.workspace_id,
                Membership.user_id == grant.owner_id,
                Membership.active.is_(True),
                Membership.role == "owner",
            )
        )
        if (
            not owner
            or grant.revoked
            or grant.expires_at <= now()
            or grant.revision != job.revision
            or scope not in grant.scopes
        ):
            raise missing()
        db.add(
            Event(
                workspace_id=job.workspace_id,
                job_id=job.id,
                actor_id=user.id,
                action="support." + scope + ".read",
                revision=job.revision,
            )
        )
        return user, job

    @app.get("/api/v1/admin/support-grants/{gid}/results")
    def support_results(gid: UUID, request: Request, db: Db, offset: int = 0) -> Json:
        _, job = support(db, request, gid, "results")
        if not 0 <= offset <= 10000:
            raise WebError(422, "PAGE_LIMIT", "Choose a bounded row page.")
        from stmtconv.web.workflow import domains

        rows = [
            {
                "statement_id": s.id,
                "id": r.id,
                "date": r.date.isoformat() if r.date else None,
                "description": r.description,
                "debit": format(r.debit, ".2f") if r.debit is not None else None,
                "credit": format(r.credit, ".2f") if r.credit is not None else None,
                "balance": format(r.balance, ".2f") if r.balance is not None else None,
                "file_id": r.source_file,
                "page": r.page,
            }
            for s in domains(snapshot(db, job).statements)
            for r in s.transactions
        ]
        return {
            "revision": job.revision,
            "items": rows[offset : offset + 100],
            "next_offset": offset + 100 if len(rows) > offset + 100 else None,
        }

    @app.get("/api/v1/admin/support-grants/{gid}/artifacts/{aid}")
    def support_artifact(gid: UUID, aid: UUID, request: Request, db: Db) -> Response:
        artifact = db.get(Artifact, aid)
        scope = "profile_scaffold" if artifact and artifact.kind == "profile_scaffold" else "source"
        _, job = support(db, request, gid, scope)
        if (
            not artifact
            or artifact.workspace_id != job.workspace_id
            or artifact.job_id != job.id
            or artifact.state != "active"
            or artifact.revision != job.revision
            or artifact.kind not in {"original", "normalized", "page", "profile_scaffold"}
        ):
            raise missing()
        data = store.verified(artifact)
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": 'attachment; filename="approved-private-source.bin"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/v1/admin/support-grants/{gid}/artifacts")
    def support_inventory(gid: UUID, request: Request, db: Db) -> Json:
        user = admin(db, request)
        grant = db.get(SupportGrant, gid)
        if not grant or grant.actor_id != user.id:
            raise missing()
        allowed: list[Json] = []
        for scope, kinds in (
            ("source", ["original", "normalized", "page"]),
            ("profile_scaffold", ["profile_scaffold"]),
        ):
            if scope in grant.scopes:
                _, job = support(db, request, gid, scope)
                allowed.extend(
                    {"id": str(a.id), "kind": a.kind, "bytes": a.bytes}
                    for a in db.scalars(
                        select(Artifact)
                        .where(
                            Artifact.workspace_id == job.workspace_id,
                            Artifact.job_id == job.id,
                            Artifact.state == "active",
                            Artifact.revision == job.revision,
                            Artifact.kind.in_(kinds),
                        )
                        .order_by(Artifact.id)
                        .limit(130)
                    )
                )
        if not allowed:
            raise missing()
        return {"items": allowed}

    @app.get("/api/v1/admin/metrics")
    def metrics(request: Request, db: Db) -> Json:
        admin(db, request)
        counts = db.execute(
            select(
                Operation.action,
                Operation.state,
                func.count(),
                func.count(func.distinct(Operation.workspace_id)),
            ).group_by(Operation.action, Operation.state)
        ).all()
        return {
            "minimum_workspaces": 5,
            "buckets": [
                {"action": a, "state": s, "count": n} for a, s, n, spaces in counts if spaces >= 5
            ],
            "suppressed_groups": sum(1 for *_, spaces in counts if spaces < 5),
            "scope": "aggregate operation outcomes; no client IDs, filenames or statement text",
        }
