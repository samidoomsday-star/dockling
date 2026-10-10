"""Phase 1 API. No upload, conversion, billing or provider calls are simulated."""

import hashlib
import hmac
import json
import re
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from stmtconv.config import HostedSettings
from stmtconv.web.auth import (
    COOKIE,
    authenticate,
    create_session,
    digest,
    is_admin,
    oauth_client,
    session_json,
    validate_write,
)
from stmtconv.web.broker import Broker
from stmtconv.web.database import PostgresUnitOfWork, UnitOfWork, database
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import Event, Invitation, Job, Membership, User, WebSession, Workspace
from stmtconv.web.pipeline_api import register_pipeline
from stmtconv.web.privacy_api import register_privacy
from stmtconv.web.repository import Cursors, HostedMetadata, Json, job_json, membership, replay
from stmtconv.web.review_api import register_review
from stmtconv.web.schemas import (
    InvitationAccept,
    InvitationCreate,
    JobOptions,
    MemberCommand,
    WorkspaceSelect,
)
from stmtconv.web.storage import ObjectStore


def create_app(config: HostedSettings) -> FastAPI:
    app = FastAPI(
        title="Dockling statement workspace", docs_url=None, redoc_url=None, openapi_url=None
    )
    engine = database(config)
    app.state.engine = engine
    uow: UnitOfWork = PostgresUnitOfWork(engine)
    identity = oauth_client(config)
    store = ObjectStore(config)
    broker = Broker(config, PostgresUnitOfWork(engine), store)
    app.state.broker = broker
    cursors = Cursors(config.session_key.get_secret_value())
    secure = config.mode == "production"
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.session_key.get_secret_value(),
        session_cookie="dockling_handshake",
        max_age=600,
        same_site="lax",
        https_only=secure,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[urlsplit(config.base_url).hostname or "invalid"]
    )

    def problem(error: WebError) -> JSONResponse:
        return JSONResponse(
            {"code": error.code, "message": error.message, "request_id": str(uuid4())},
            status_code=error.status,
        )

    @app.exception_handler(WebError)
    async def web_error(_request: Request, error: WebError) -> JSONResponse:
        return problem(error)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _error: RequestValidationError) -> JSONResponse:
        return problem(WebError(422, "INPUT_INVALID", "Check the submitted fields and try again."))

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
        return problem(
            WebError(503, "DATABASE_UNAVAILABLE", "The service is temporarily unavailable.")
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        return problem(
            WebError(
                error.status_code,
                "NOT_FOUND" if error.status_code == 404 else "REQUEST_DENIED",
                "This request is unavailable.",
            )
        )

    @app.middleware("http")
    async def boundaries(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH"}:
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                maximum = (
                    config.upload_bytes
                    if (
                        request.method == "POST"
                        and (
                            re.fullmatch(r"/api/v1/jobs/[0-9a-fA-F-]{36}/files", request.url.path)
                            or re.fullmatch(
                                r"/api/v1/jobs/[0-9a-fA-F-]{36}/review-workbooks/[0-9a-fA-F-]{36}/apply",
                                request.url.path,
                            )
                        )
                    )
                    else 65536
                )
                if size > maximum:
                    return problem(
                        WebError(413, "BODY_LIMIT", "The submitted request is too large.")
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        try:
            response = await call_next(request)
        except Exception:
            # Do not let provider/DB exception internals reach an access log or response.
            response = problem(
                WebError(503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable.")
            )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    def get_db() -> Iterator[Session]:
        with uow.transaction() as db:
            yield db

    Db = Annotated[Session, Depends(get_db, scope="function")]
    # Local annotations must be concrete: FastAPI resolves function annotations in globals.

    def actor(db: Session, request: Request, *, write: bool = False) -> tuple[WebSession, User]:
        s, u = authenticate(db, request)
        if write:
            validate_write(config, request, s)
        return s, u

    def scoped(
        db: Session, request: Request, *, write: bool = False, owner: bool = False
    ) -> tuple[UUID, User]:
        s, u = actor(db, request, write=write)
        m = membership(db, s.workspace_id, u.id, write=write, owner=owner)
        return m.workspace_id, u

    def key(request: Request) -> str:
        value = request.headers.get("idempotency-key", "")
        if not value or len(value) > 128 or not value.isascii() or any(ord(c) < 33 for c in value):
            raise WebError(400, "REQUEST_KEY_REQUIRED", "A valid request key is required.")
        return value

    def member_json(m: Membership) -> Json:
        return {
            "id": str(m.id),
            "display_name": "Member " + str(m.user_id)[:8],
            "role": m.role,
            "active": m.active,
            "version": m.version,
        }

    def invite_token(i: UUID) -> str:
        return hmac.new(
            config.session_key.get_secret_value().encode(),
            ("invite:" + str(i)).encode(),
            hashlib.sha256,
        ).hexdigest()

    def invite_json(inv: Invitation) -> Json:
        return {
            "id": str(inv.id),
            "role": inv.role,
            "expires_at": inv.expires_at.isoformat(),
            "status": inv.status,
        }

    @app.get("/auth/login")
    async def login(request: Request) -> Response:
        request.session.clear()
        try:
            return cast(
                Response,
                await identity.authorize_redirect(request, config.base_url + "/auth/callback"),
            )
        except Exception:
            raise WebError(
                503, "IDENTITY_UNAVAILABLE", "Sign-in is temporarily unavailable."
            ) from None

    @app.get("/auth/callback")
    async def callback(request: Request, db: Db) -> Response:
        try:
            state = request.query_params.get("state", "")
            if not state or len(state) > 500:
                raise ValueError
            saved = await identity.framework.get_state_data(request.session, state)
            expected_nonce = saved.get("nonce") if isinstance(saved, dict) else None
            if not expected_nonce:
                raise ValueError
            token = await identity.authorize_access_token(
                request,
                leeway=30,
                claims_options={
                    "iss": {"essential": True, "value": config.oidc_issuer},
                    "aud": {"essential": True, "value": config.oidc_client_id},
                    "exp": {"essential": True},
                    "iat": {"essential": True},
                    "nonce": {"essential": True},
                },
            )
            claims = dict(token["userinfo"])
            if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(
                claims["nonce"], expected_nonce
            ):
                raise ValueError
            value = create_session(config, db, claims)
        except SQLAlchemyError:
            raise
        except Exception:
            raise WebError(
                401, "LOGIN_INVALID", "Sign-in could not be verified. Start sign-in again."
            ) from None
        finally:
            request.session.clear()
        response = RedirectResponse("/app", status_code=303)
        response.set_cookie(
            COOKIE,
            value,
            max_age=config.session_hours * 3600,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
        return response

    @app.get("/api/v1/version")
    def version() -> Json:
        return {"version": "0.2.0-pipeline", "api_version": "v1"}

    @app.get("/api/v1/session")
    def current(request: Request, db: Db) -> Json:
        s, u = actor(db, request)
        return session_json(config, db, s, u)

    @app.post("/api/v1/session/logout", status_code=204)
    def logout(request: Request, db: Db) -> Response:
        s, _u = actor(db, request, write=True)
        s.revoked = True
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=secure)
        return response

    @app.get("/api/v1/workspaces")
    def workspaces(
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
    ) -> Json:
        _s, u = actor(db, request)
        scope = "workspaces:" + str(u.id)
        after = cursors.decode(cursor, scope)
        q = (
            select(Workspace, Membership)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == u.id, Membership.active.is_(True))
        )
        if after:
            q = q.where(Workspace.id > after)
        rows = db.execute(q.order_by(Workspace.id).limit(limit + 1)).all()
        return {
            "items": [{"id": str(w.id), "name": w.name, "role": m.role} for w, m in rows[:limit]],
            "next_cursor": cursors.encode(rows[limit - 1][0].id, scope)
            if len(rows) > limit
            else None,
        }

    @app.post("/api/v1/session/workspace")
    def switch(body: WorkspaceSelect, request: Request, db: Db) -> Json:
        s, u = actor(db, request, write=True)
        membership(db, body.workspace_id, u.id)
        s.workspace_id = body.workspace_id
        return session_json(config, db, s, u)

    @app.get("/api/v1/jobs")
    def jobs(
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
        search: Annotated[str, Query(max_length=100)] = "",
    ) -> Json:
        ws, _u = scoped(db, request)
        scope = "jobs:" + str(ws) + ":" + search
        after = cursors.decode(cursor, scope)
        q = select(Job).where(Job.workspace_id == ws, Job.deletion_state == "active")
        if search:
            q = q.where(func.lower(Job.name).contains(search.lower(), autoescape=True))
        if after:
            q = q.where(Job.id > after)
        rows = list(db.scalars(q.order_by(Job.id).limit(limit + 1)))
        return {
            "items": [
                {
                    k: v
                    for k, v in job_json(j).items()
                    if k
                    in {
                        "id",
                        "name",
                        "status",
                        "revision",
                        "currency",
                        "created_at",
                        "deletion_state",
                    }
                }
                for j in rows[:limit]
            ],
            "next_cursor": cursors.encode(rows[limit - 1].id, scope) if len(rows) > limit else None,
        }

    @app.post("/api/v1/jobs", status_code=201)
    def create_job(body: JobOptions, request: Request, db: Db) -> Json:
        ws, u = scoped(db, request, write=True)
        return replay(
            db,
            ws,
            u.id,
            "job.create",
            key(request),
            body.model_dump(mode="json"),
            lambda: HostedMetadata(db, ws, u.id).create(body),
        )

    @app.get("/api/v1/jobs/{job}")
    def get_job(job: UUID, request: Request, db: Db) -> Json:
        ws, u = scoped(db, request)
        return HostedMetadata(db, ws, u.id).get(job)

    @app.get("/api/v1/jobs/{job}/activity")
    def activity(
        job: UUID,
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
    ) -> Json:
        ws, u = scoped(db, request)
        HostedMetadata(db, ws, u.id).get(job)
        scope = f"activity:{ws}:{job}"
        after = cursors.decode(cursor, scope)
        q = select(Event).where(Event.workspace_id == ws, Event.job_id == job)
        if after:
            q = q.where(Event.id > after)
        rows = list(db.scalars(q.order_by(Event.id).limit(limit + 1)))
        return {
            "items": [
                {
                    "id": str(e.id),
                    "at": e.at.isoformat(),
                    "action": e.action,
                    "actor_id": str(e.actor_id) if e.actor_id else None,
                    "revision": e.revision,
                    "code": e.code,
                }
                for e in rows[:limit]
            ],
            "next_cursor": cursors.encode(rows[limit - 1].id, scope) if len(rows) > limit else None,
        }

    @app.get("/api/v1/members")
    def members(
        request: Request,
        db: Db,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query(max_length=500)] = None,
    ) -> Json:
        ws, _u = scoped(db, request, owner=True)
        scope = "members:" + str(ws)
        after = cursors.decode(cursor, scope)
        q = select(Membership).where(Membership.workspace_id == ws)
        if after:
            q = q.where(Membership.id > after)
        rows = list(db.scalars(q.order_by(Membership.id).limit(limit + 1)))
        return {
            "items": [member_json(m) for m in rows[:limit]],
            "next_cursor": cursors.encode(rows[limit - 1].id, scope) if len(rows) > limit else None,
        }

    @app.patch("/api/v1/members/{member}")
    def change_member(member: UUID, body: MemberCommand, request: Request, db: Db) -> Json:
        ws, u = scoped(db, request, write=True, owner=True)

        def execute() -> Json:
            target = db.scalar(
                select(Membership).where(Membership.workspace_id == ws, Membership.id == member)
            )
            if target is None:
                raise missing()
            if target.version != body.expected_version:
                raise WebError(409, "STALE_VERSION", "Refresh the team before making this change.")
            role = body.role if body.role is not None else target.role
            active = body.active if body.active is not None else target.active
            if target.role == "owner" and target.active and (role != "owner" or not active):
                count = db.scalar(
                    select(func.count())
                    .select_from(Membership)
                    .where(
                        Membership.workspace_id == ws,
                        Membership.role == "owner",
                        Membership.active.is_(True),
                    )
                )
                if count is None or count <= 1:
                    raise WebError(409, "FINAL_OWNER", "Keep at least one active workspace owner.")
            target.role = role
            target.active = active
            target.version += 1
            db.add(Event(workspace_id=ws, actor_id=u.id, action="member.changed"))
            return member_json(target)

        return replay(
            db,
            ws,
            u.id,
            "member.change:" + str(member),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.post("/api/v1/invitations", status_code=201)
    def invite(body: InvitationCreate, request: Request, db: Db) -> Json:
        ws, u = scoped(db, request, write=True, owner=True)

        def execute() -> Json:
            i = uuid4()
            record = Invitation(
                id=i,
                workspace_id=ws,
                email=body.email.casefold(),
                role=body.role,
                token_hash=digest(invite_token(i)),
                expires_at=datetime.now(UTC) + timedelta(days=2),
                status="pending",
            )
            db.add(record)
            db.flush()
            db.add(Event(workspace_id=ws, actor_id=u.id, action="invitation.created"))
            return invite_json(record)

        result = dict(
            replay(
                db,
                ws,
                u.id,
                "invitation.create",
                key(request),
                body.model_dump(mode="json"),
                execute,
            )
        )
        result["accept_url"] = config.base_url + "/invite#" + invite_token(UUID(str(result["id"])))
        return result

    @app.delete("/api/v1/invitations/{invitation}", status_code=204)
    def revoke(invitation: UUID, request: Request, db: Db) -> Response:
        ws, u = scoped(db, request, write=True, owner=True)

        def execute() -> Json:
            target = db.scalar(
                select(Invitation).where(Invitation.workspace_id == ws, Invitation.id == invitation)
            )
            if target is None:
                raise missing()
            if target.status != "pending":
                raise WebError(
                    409, "INVITATION_UNAVAILABLE", "This invitation is no longer pending."
                )
            target.status = "revoked"
            db.add(Event(workspace_id=ws, actor_id=u.id, action="invitation.revoked"))
            return {}

        replay(db, ws, u.id, "invitation.revoke:" + str(invitation), key(request), {}, execute)
        return Response(status_code=204)

    @app.post("/api/v1/invitations/accept")
    def accept(body: InvitationAccept, request: Request, db: Db) -> Json:
        s, u = actor(db, request, write=True)
        inv = db.scalar(select(Invitation).where(Invitation.token_hash == digest(body.token)))
        if inv is None or not u.email_verified or not u.email or inv.email != u.email.casefold():
            raise missing()
        # Workspace lock serializes accept/revoke/member changes using one lock order.
        db.execute(
            select(Workspace.id).where(Workspace.id == inv.workspace_id).with_for_update()
        ).first()
        db.refresh(inv)

        def execute() -> Json:
            if inv.status != "pending" or inv.expires_at <= datetime.now(UTC):
                raise missing()
            existing = db.scalar(
                select(Membership).where(
                    Membership.workspace_id == inv.workspace_id, Membership.user_id == u.id
                )
            )
            if existing is not None:
                raise WebError(
                    409,
                    "MEMBERSHIP_EXISTS",
                    "Ask the workspace owner to update your existing membership.",
                )
            db.add(Membership(workspace_id=inv.workspace_id, user_id=u.id, role=inv.role))
            inv.status = "accepted"
            workspace = db.get(Workspace, inv.workspace_id)
            assert workspace is not None
            db.add(
                Event(workspace_id=inv.workspace_id, actor_id=u.id, action="invitation.accepted")
            )
            return {"id": str(inv.workspace_id), "name": workspace.name, "role": inv.role}

        result = replay(
            db,
            inv.workspace_id,
            u.id,
            "invitation.accept:" + str(inv.id),
            key(request),
            {"token_hash": digest(body.token)},
            execute,
        )
        # Select only after confirming membership still active (including command replay).
        db.flush()
        membership(db, inv.workspace_id, u.id)
        s.workspace_id = inv.workspace_id
        return result

    @app.get("/api/v1/settings")
    def settings(request: Request, db: Db) -> Json:
        ws, _u = scoped(db, request)
        workspace = db.get(Workspace, ws)
        assert workspace is not None
        return {
            "version": workspace.version,
            "currency": "USD",
            "date_order": "auto",
            "output_date_format": "ISO",
            "outputs": ["excel", "csv"],
            "retention_days": None,
        }

    @app.get("/api/v1/admin/health")
    def health(request: Request, db: Db) -> Json:
        s, u = actor(db, request)
        if not is_admin(config, s, u):
            raise WebError(
                403,
                "ADMIN_MFA_REQUIRED",
                "Administrator access requires a fresh verified second-factor sign-in.",
            )
        db.execute(text("SELECT 1"))
        return {
            "database": "healthy",
            "storage": "healthy" if store.healthy() else "unhealthy",
            "worker": "unknown",
            "models": "unknown",
        }

    register_pipeline(app, config, get_db, scoped, key, store, broker, cursors)
    register_review(app, config, get_db, scoped, key, store)
    register_privacy(app, config, get_db, scoped, key)

    # API is registered before the SPA. Unknown API/auth URLs cannot serve HTML or fixtures.
    @app.api_route("/api/{remaining:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def future(remaining: str) -> Json:
        raise missing()

    dist = Path(config.frontend_dist)
    try:
        api_build = json.loads((dist / "dockling-mode.json").read_text()).get("mode") == "api"
    except (OSError, ValueError):
        api_build = False
    if api_build and (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str) -> FileResponse:
        if (
            path.startswith(("api/", "auth/"))
            or not api_build
            or not (dist / "index.html").is_file()
        ):
            raise missing()
        return FileResponse(dist / "index.html")

    return app
