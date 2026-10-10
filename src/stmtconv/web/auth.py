"""Maintained OIDC verification plus opaque, revocable PostgreSQL sessions."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.errors import WebError
from stmtconv.web.models import Membership, User, WebSession
from stmtconv.web.repository import Json

COOKIE = "dockling_session"


def oauth_client(config: HostedSettings) -> Any:
    oauth = OAuth()
    oauth.register(
        name="identity",
        client_id=config.oidc_client_id,
        client_secret=config.oidc_client_secret.get_secret_value(),
        server_metadata_url=config.oidc_issuer + "/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
            "timeout": 5,
        },
        claims_options={
            "iss": {"essential": True, "value": config.oidc_issuer},
            "aud": {"essential": True, "value": config.oidc_client_id},
        },
    )
    return oauth.identity


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, request: Request) -> tuple[WebSession, User]:
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 150:
        raise WebError(401, "SIGN_IN_REQUIRED", "Please sign in again.")
    result = db.execute(
        select(WebSession, User)
        .join(User, WebSession.user_id == User.id)
        .where(
            WebSession.token_hash == digest(token),
            WebSession.revoked.is_(False),
            WebSession.expires_at > datetime.now(UTC),
        )
    ).first()
    if result is None:
        raise WebError(401, "SIGN_IN_REQUIRED", "Please sign in again.")
    session, user = result
    return session, user


def csrf(config: HostedSettings, session: WebSession) -> str:
    return hmac.new(
        config.session_key.get_secret_value().encode(),
        ("csrf:" + session.token_hash).encode(),
        hashlib.sha256,
    ).hexdigest()


def validate_write(config: HostedSettings, request: Request, session: WebSession) -> None:
    if (
        request.headers.get("origin") != config.base_url
        or not request.headers.get("x-csrf-token", "").isascii()
        or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf(config, session))
    ):
        raise WebError(403, "CSRF_DENIED", "Refresh the page before trying this action again.")


def is_admin(config: HostedSettings, session: WebSession, user: User) -> bool:
    return (
        user.issuer == config.oidc_issuer
        and user.subject in config.admin_subjects
        and session.mfa
        and session.mfa_until is not None
        and session.mfa_until > datetime.now(UTC)
    )


def session_json(config: HostedSettings, db: Session, session: WebSession, user: User) -> Json:
    member = db.scalar(
        select(Membership).where(
            Membership.workspace_id == session.workspace_id,
            Membership.user_id == user.id,
            Membership.active.is_(True),
        )
    )
    return {
        "user_id": str(user.id),
        "workspace_id": str(session.workspace_id) if member else None,
        "role": member.role if member else None,
        "platform_admin": is_admin(config, session, user),
        "csrf_token": csrf(config, session),
        "expires_at": session.expires_at.isoformat(),
    }


def create_session(config: HostedSettings, db: Session, claims: dict[str, Any]) -> str:
    # These claims must come from Authlib's verified ID token, not a browser body/userinfo fetch.
    if claims.get("iss") != config.oidc_issuer or not isinstance(claims.get("sub"), str):
        raise WebError(401, "LOGIN_INVALID", "Sign-in could not be verified.")
    email = claims.get("email")
    email = email if isinstance(email, str) and len(email) <= 254 else None
    verified = claims.get("email_verified") is True
    user_id = db.scalar(
        insert(User)
        .values(
            issuer=config.oidc_issuer, subject=claims["sub"], email=email, email_verified=verified
        )
        .on_conflict_do_update(
            index_elements=[User.issuer, User.subject],
            set_={"email": email, "email_verified": verified},
        )
        .returning(User.id)
    )
    assert user_id is not None
    user = db.get(User, user_id, populate_existing=True)
    assert user is not None
    member = db.scalar(
        select(Membership)
        .where(Membership.user_id == user.id, Membership.active.is_(True))
        .order_by(Membership.workspace_id)
    )
    token = secrets.token_urlsafe(32)
    amr = claims.get("amr", [])
    mfa = isinstance(amr, list) and any(x in config.mfa_amr for x in amr)
    now = datetime.now(UTC)
    db.add(
        WebSession(
            token_hash=digest(token),
            user_id=user.id,
            workspace_id=member.workspace_id if member else None,
            expires_at=now + timedelta(hours=config.session_hours),
            mfa=mfa,
            mfa_until=now + timedelta(minutes=5) if mfa else None,
        )
    )
    return token
