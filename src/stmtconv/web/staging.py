"""Read-only staging preflight. Passing this is never launch or accuracy approval."""

import json
import stat
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from joserfc.jwk import KeySet, KeySetSerialization
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from stmtconv.config import HostedSettings
from stmtconv.web.database import database
from stmtconv.web.storage import ObjectStore
from stmtconv.web.tls import service_tls


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    status: Literal["passed", "failed"]


class Preflight(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: Literal["read_only_staging_preflight"] = "read_only_staging_preflight"
    checked_at: datetime
    status: Literal["passed", "failed"]
    launch_approval: Literal["not_assessed"] = "not_assessed"
    checks: list[Check]


def private_file(path: Path) -> bool:
    try:
        details = path.lstat()
        return (
            stat.S_ISREG(details.st_mode)
            and details.st_mode & 0o077 == 0
            and details.st_size <= 64 * 1024
        )
    except OSError:
        return False


def head_revision() -> str:
    settings = Config()
    settings.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    revision = ScriptDirectory.from_config(settings).get_current_head()
    if revision is None:
        raise ValueError("Schema head missing")
    return revision


def database_check(config: HostedSettings) -> bool:
    engine = database(config)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '5000ms'"))
            secure = connection.scalar(
                text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            )
            revisions = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
            return secure is True and revisions == [head_revision()]
    finally:
        engine.dispose()


def _read(client: httpx.Client, url: str) -> httpx.Response:
    # Never follow an HTTP downgrade or redirects to a different private service.
    start = time.monotonic()
    with client.stream("GET", url, follow_redirects=False) as response:
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > 64 * 1024 or time.monotonic() - start > 15:
                raise ValueError("Readiness response exceeds limits")
        # iter_bytes() already decodes gzip. Preserve security headers without decoding twice.
        headers = httpx.Headers(response.headers)
        headers.pop("content-encoding", None)
        headers.pop("content-length", None)
        return httpx.Response(
            response.status_code,
            headers=headers,
            content=bytes(body),
            request=response.request,
        )


def _headers(response: httpx.Response) -> bool:
    directives = {
        part.strip().split()[0]: part.strip().split()[1:]
        for part in response.headers.get("content-security-policy", "").split(";")
        if part.strip()
    }
    cache = {x.strip().lower() for x in response.headers.get("cache-control", "").split(",")}
    hsts = response.headers.get("strict-transport-security", "").lower().split(";")
    return (
        {"private", "no-store"} <= cache
        and response.headers.get("x-content-type-options") == "nosniff"
        and response.headers.get("referrer-policy") == "no-referrer"
        and directives.get("default-src") == ["'self'"]
        and directives.get("frame-ancestors") == ["'none'"]
        and "max-age=31536000" in {x.strip() for x in hsts}
    )


def _origin(value: str) -> tuple[str, str, int | None]:
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError("Invalid identity endpoint")
    return url.scheme, url.hostname, url.port or 443


def identity_check(client: httpx.Client, config: HostedSettings) -> bool:
    response = _read(client, config.oidc_issuer + "/.well-known/openid-configuration")
    if response.status_code != 200:
        return False
    metadata = response.json()
    if not isinstance(metadata, dict) or metadata.get("issuer") != config.oidc_issuer:
        return False
    for name in ["authorization_endpoint", "token_endpoint", "jwks_uri"]:
        value = metadata.get(name)
        if not isinstance(value, str) or _origin(value) != _origin(config.oidc_issuer):
            return False
    if "S256" not in metadata.get("code_challenge_methods_supported", []):
        return False
    keys = _read(client, metadata["jwks_uri"])
    value = keys.json() if keys.status_code == 200 else None
    if not isinstance(value, dict) or not isinstance(value.get("keys"), list) or not value["keys"]:
        return False
    for key in value["keys"]:
        if not isinstance(key, dict) or key.get("kty") not in {"RSA", "EC", "OKP"}:
            return False
        if {"d", "p", "q", "dp", "dq", "qi", "k"}.intersection(key):
            return False
    KeySet.import_key_set(cast(KeySetSerialization, value))
    return True


def login_check(client: httpx.Client, config: HostedSettings) -> bool:
    response = _read(client, config.base_url + "/auth/login")
    if response.status_code not in {302, 303, 307} or not _headers(response):
        return False
    redirect = response.headers.get("location", "")
    metadata = _read(client, config.oidc_issuer + "/.well-known/openid-configuration").json()
    target = urlsplit(redirect)
    endpoint = urlsplit(metadata["authorization_endpoint"])
    query = parse_qs(target.query)
    cookie = response.headers.get("set-cookie", "").lower()
    return (
        _origin(redirect) == _origin(config.oidc_issuer)
        and target.path == endpoint.path
        and query.get("client_id") == [config.oidc_client_id]
        and query.get("redirect_uri") == [config.base_url + "/auth/callback"]
        and query.get("response_type") == ["code"]
        and query.get("code_challenge_method") == ["S256"]
        and bool(query.get("code_challenge"))
        and bool(query.get("state"))
        and bool(query.get("nonce"))
        and cookie.startswith("dockling_handshake=")
        and {"secure", "httponly", "samesite=lax"} <= {s.strip() for s in cookie.split(";")}
    )


def preflight(config: HostedSettings) -> Preflight:
    checks: list[Check] = []

    def check(code: str, action: Callable[[], bool]) -> None:
        try:
            ok = action()
        except Exception:
            # A TLS, HTTP, driver or SDK error may include URLs, SQL or credentials.
            ok = False
        checks.append(Check(code=code, status="passed" if ok else "failed"))

    check("PRODUCTION_CONFIGURATION", lambda: config.mode == "production")
    if config.mode != "production":
        return Preflight(checked_at=datetime.now(UTC), status="failed", checks=checks)
    check("BYOK_VAULT_CONFIGURED", lambda: config.ai_encryption_key is not None)
    check(
        "APPLICATION_DATABASE_IDENTITY",
        lambda: urlsplit(config.database_url.get_secret_value()).username == "dockling_app",
    )
    check("VERIFIED_DATABASE_TLS_AND_SCHEMA", lambda: database_check(config))
    check("AUTHENTICATED_STORAGE_HEAD", lambda: ObjectStore(config).healthy())
    try:
        client = httpx.Client(verify=service_tls(config), timeout=5, trust_env=False)
    except Exception:
        checks.append(Check(code="SERVICE_TLS_TRUST", status="failed"))
    else:
        with client:

            def health(path: str, status: str) -> bool:
                response = _read(client, config.base_url + path)
                return (
                    response.status_code == 200
                    and response.json() == {"status": status}
                    and _headers(response)
                )

            check("HTTPS_LIVENESS_AND_HEADERS", lambda: health("/api/v1/health/live", "alive"))
            check("API_STORAGE_WORKER_READINESS", lambda: health("/api/v1/health/ready", "ready"))
            for path, code in [("/api/v1/jobs", "jobs"), ("/api/v1/admin/operations", "admin")]:

                def denied(path: str = path) -> bool:
                    response = _read(client, config.base_url + path)
                    return response.status_code == 401 and _headers(response)

                check("ANONYMOUS_" + code.upper() + "_DENIED", denied)

            def listing_denied() -> bool:
                response = _read(
                    client,
                    config.s3_endpoint.rstrip("/")
                    + "/"
                    + quote(config.s3_bucket, safe="")
                    + "?list-type=2&max-keys=0",
                )
                return response.status_code in {401, 403}

            check("ANONYMOUS_BUCKET_LISTING_DENIED", listing_denied)
            check("VERIFIED_OIDC_DISCOVERY_AND_KEYS", lambda: identity_check(client, config))
            check("LOGIN_PKCE_CALLBACK_SECURE_COOKIE", lambda: login_check(client, config))

            def frontend() -> bool:
                response = _read(client, config.base_url + "/")
                return (
                    response.status_code == 200
                    and "text/html" in response.headers.get("content-type", "")
                    and "<!doctype html>" in response.text.lower()
                    and _headers(response)
                )

            check("HTTPS_FRONTEND_DOCUMENT", frontend)
    return Preflight(
        checked_at=datetime.now(UTC),
        status="passed" if all(c.status == "passed" for c in checks) else "failed",
        checks=checks,
    )


def report_json(report: Preflight) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2)
