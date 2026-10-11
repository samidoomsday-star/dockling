"""Actual verified TLS transports plus fail-closed staging and field-record checks."""

import asyncio
import gzip
import importlib.util
import json
import ssl
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from joserfc.jwk import RSAKey
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import DBAPIError

from stmtconv.config import HostedSettings, WorkerSettings
from stmtconv.web.auth import oauth_client
from stmtconv.web.database import database, migrate, worker_database
from stmtconv.web.field_validation import FieldRun, observations
from stmtconv.web.staging import _read, database_check, head_revision, preflight, report_json
from stmtconv.web.storage import ObjectStore
from stmtconv.web.tls import service_tls


def test_preflight_materializes_decoded_gzip_once_and_retains_limits() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        payload = b'{"status":"alive"}' if request.url.path == "/small" else b"x" * 65537
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
            content=gzip.compress(payload),
        )

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        response = _read(client, "https://example.test/small")
        assert response.json() == {"status": "alive"}
        assert response.headers["content-type"] == "application/json"
        with pytest.raises(ValueError, match="exceeds limits"):
            _read(client, "https://example.test/large")


def certificates(folder: Path, *, expired: bool = False) -> None:
    now = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic staging test CA")])
    root = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now - timedelta(minutes=1) if expired else now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    (folder / "ca.pem").write_bytes(root.public_bytes(serialization.Encoding.PEM))
    (folder / "server.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    (folder / "ca.pem").chmod(0o644)
    (folder / "server.pem").chmod(0o644)
    (folder / "server.key").write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (folder / "server.key").chmod(0o600)


def settings(origin: str, ca: Path | None) -> HostedSettings:
    return HostedSettings(
        mode="production",
        database_url="postgresql+pg8000://dockling_app:fictional@localhost/db",
        session_key="fictional-session-" + "a" * 32,
        ai_encryption_key="b" * 64,
        base_url=origin,
        oidc_issuer=origin + "/identity",
        oidc_client_secret="fictional-oidc-" + "c" * 32,
        s3_endpoint=origin,
        s3_access_key="fictional-access",
        s3_secret_key="d" * 32,
        tls_ca_file=ca,
    )


@pytest.fixture
def tls_service(tmp_path):
    certificates(tmp_path)
    state = {
        "ready": True,
        "anonymous_allowed": False,
        "secure_cookie": True,
        "headers": True,
        "identity_same_origin": True,
        "large": False,
    }
    origin = ""
    signing_key = RSAKey.generate_key(2048).as_dict(private=False)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def do_GET(self):
            status, value, content_type = 200, {}, "application/json"
            location = None
            if self.path == "/api/v1/health/live":
                value = {"status": "alive"}
            elif self.path == "/api/v1/health/ready":
                status = 200 if state["ready"] else 503
                value = {"status": "ready" if state["ready"] else "unavailable"}
            elif self.path in {"/api/v1/jobs", "/api/v1/admin/operations"}:
                status = 200 if state["anonymous_allowed"] else 401
            elif self.path.startswith("/dockling-private?"):
                status = 200 if state["anonymous_allowed"] else 403
            elif self.path == "/identity/.well-known/openid-configuration":
                value = {
                    "issuer": origin + "/identity",
                    "authorization_endpoint": origin + "/authorize",
                    "token_endpoint": origin + "/token",
                    "jwks_uri": origin + "/keys",
                    "code_challenge_methods_supported": ["S256"],
                }
                if not state["identity_same_origin"]:
                    value["jwks_uri"] = "http://untrusted.example/keys"
            elif self.path == "/keys":
                value = {"keys": [signing_key]}
            elif self.path == "/auth/login":
                status = 302
                location = (
                    origin
                    + "/authorize?"
                    + urlencode(
                        {
                            "client_id": "dockling-web",
                            "redirect_uri": origin + "/auth/callback",
                            "response_type": "code",
                            "code_challenge_method": "S256",
                            "code_challenge": "fictional",
                            "state": "fictional",
                            "nonce": "fictional",
                        }
                    )
                )
            elif self.path == "/":
                value, content_type = (
                    "<!doctype html><html><body>Synthetic test</body></html>",
                    "text/html",
                )
            else:
                status = 404
            body = value.encode() if isinstance(value, str) else json.dumps(value).encode()
            if state["large"]:
                body = b"x" * (64 * 1024 + 1)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if state["headers"]:
                self.send_header("Cache-Control", "private, no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'"
                )
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            if location:
                self.send_header("Location", location)
                cookie = "dockling_handshake=fictional; HttpOnly; SameSite=lax"
                self.send_header(
                    "Set-Cookie", cookie + ("; Secure" if state["secure_cookie"] else "")
                )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "server.pem", tmp_path / "server.key")
    state["tls_context"] = context
    server.socket = context.wrap_socket(server.socket, server_side=True)
    origin = "https://localhost:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield settings(origin, tmp_path / "ca.pem"), state, tmp_path
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_explicit_ca_verifies_http_oidc_and_storage(tls_service):
    config, _, _ = tls_service
    with httpx.Client(verify=service_tls(config), trust_env=False) as client:
        assert client.get(config.base_url).status_code == 200
    assert asyncio.run(oauth_client(config).load_server_metadata())["issuer"] == config.oidc_issuer
    assert ObjectStore(config).healthy()
    with httpx.Client(trust_env=False) as client, pytest.raises(httpx.ConnectError):
        client.get(config.base_url)
    with httpx.Client(verify=service_tls(config), trust_env=False) as client:
        with pytest.raises(httpx.ConnectError):
            client.get(config.base_url.replace("localhost", "127.0.0.1"))
    assert not ObjectStore(config.model_copy(update={"tls_ca_file": None})).healthy()


def test_expired_server_certificate_is_rejected(tls_service):
    config, state, folder = tls_service
    certificates(folder, expired=True)
    state["tls_context"].load_cert_chain(folder / "server.pem", folder / "server.key")
    with httpx.Client(verify=service_tls(config), trust_env=False) as client:
        with pytest.raises(httpx.ConnectError, match="certificate has expired"):
            client.get(config.base_url)
    assert not ObjectStore(config).healthy()


def test_verified_preflight_and_fixed_failure_reports(tls_service, monkeypatch):
    config, state, _ = tls_service
    monkeypatch.setattr("stmtconv.web.staging.database_check", lambda _config: True)
    result = preflight(config)
    assert result.status == "passed"
    assert result.launch_approval == "not_assessed"
    for flag, code in [
        ("ready", "API_STORAGE_WORKER_READINESS"),
        ("secure_cookie", "LOGIN_PKCE_CALLBACK_SECURE_COOKIE"),
        ("headers", "HTTPS_LIVENESS_AND_HEADERS"),
        ("identity_same_origin", "VERIFIED_OIDC_DISCOVERY_AND_KEYS"),
    ]:
        state[flag] = False
        result = preflight(config)
        assert result.status == "failed"
        assert next(x.status for x in result.checks if x.code == code) == "failed"
        state[flag] = True
    state["anonymous_allowed"] = True
    result = preflight(config)
    assert result.status == "failed"
    assert all(x.status == "failed" for x in result.checks if "DENIED" in x.code)
    output = report_json(result)
    assert "fictional" not in output and "localhost" not in output and "handshake" not in output
    state["anonymous_allowed"] = False
    state["large"] = True
    assert preflight(config).status == "failed"


def test_local_mode_refuses_staging_checks_without_network(configs, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Must not probe local services as staging")

    monkeypatch.setattr("stmtconv.web.staging.database_check", forbidden)
    monkeypatch.setattr("stmtconv.web.staging.httpx.Client", forbidden)
    result = preflight(configs[0])
    assert result.status == "failed"
    assert [x.code for x in result.checks] == ["PRODUCTION_CONFIGURATION"]


def test_private_ca_path_and_service_origins_required(tmp_path):
    with pytest.raises(ValidationError):
        settings("https:///missing-host", None)
    with pytest.raises(ValidationError):
        settings("https://localhost", tmp_path / "missing.pem")
    with pytest.raises(ValidationError):
        WorkerSettings(
            database_url="postgresql+pg8000://dockling_worker:fictional@localhost/db",
            tls_ca_file=Path("relative.pem"),
        )


def test_real_postgres_migrations_and_worker_verify_tls(tmp_path):
    from sqlalchemy import text

    certificates(tmp_path)
    # Public certificate directory is traversable by the different container UID;
    # the synthetic password and key files remain 0600.
    tmp_path.chmod(0o755)
    name = "dockling-tls-test-" + uuid4().hex[:12]
    env = tmp_path / "postgres.env"
    env.write_text("POSTGRES_PASSWORD=fictional-tls-test-password\n")
    env.chmod(0o600)
    image = "postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
    engine = None
    worker = None
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--env-file",
                str(env),
                "-p",
                "127.0.0.1::5432",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=256m",
                "--tmpfs",
                "/tmp:rw,size=16m",
                "--mount",
                f"type=bind,source={tmp_path},target=/fixtures,readonly",
                "--entrypoint",
                "/bin/bash",
                image,
                "-c",
                "cp /fixtures/server.key /tmp/server.key; chown postgres:postgres /tmp/server.key; "
                "chmod 600 /tmp/server.key; exec docker-entrypoint.sh postgres -c ssl=on "
                "-c ssl_cert_file=/fixtures/server.pem -c ssl_key_file=/tmp/server.key",
            ],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, "Synthetic TLS database could not start"
        published = subprocess.run(
            ["docker", "port", name, "5432"], capture_output=True, text=True, check=True
        ).stdout.strip()
        port = int(published.rsplit(":", 1)[1])
        config = settings("https://localhost", tmp_path / "ca.pem").model_copy(
            update={
                "database_url": SecretStr(
                    f"postgresql+pg8000://postgres:fictional-tls-test-password@localhost:{port}/postgres"
                ),
            }
        )
        engine = database(config)
        for attempt in range(100):
            try:
                with engine.begin() as connection:
                    assert (
                        connection.scalar(
                            text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                        )
                        is True
                    )
                break
            except Exception as error:
                if attempt == 99:
                    # Only this disposable probe uses fictional credentials.
                    diagnostic = tmp_path / "tls-probe.log"
                    diagnostic.write_text(
                        subprocess.run(
                            ["docker", "logs", name], capture_output=True, text=True
                        ).stderr
                        + "\n"
                        + repr(error)
                    )
                    diagnostic.chmod(0o600)
                    raise AssertionError("Synthetic PostgreSQL TLS never became ready") from None
                time.sleep(0.2)
        with engine.begin() as connection:
            connection.execute(
                text("CREATE ROLE dockling_app LOGIN PASSWORD 'fictional-app-test-password'")
            )
            connection.execute(
                text("CREATE ROLE dockling_worker LOGIN PASSWORD 'fictional-worker-test-password'")
            )
        migrate(config)
        migrate(config)
        app_config = config.model_copy(
            update={
                "database_url": SecretStr(
                    f"postgresql+pg8000://dockling_app:fictional-app-test-password@localhost:{port}/postgres"
                ),
            }
        )
        assert database_check(app_config)
        with engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == head_revision()
            )
        worker_config = WorkerSettings(
            mode="production",
            tls_ca_file=tmp_path / "ca.pem",
            database_url=f"postgresql+pg8000://dockling_worker:fictional-worker-test-password@localhost:{port}/postgres",
        )
        worker = worker_database(worker_config)
        with worker.connect() as connection:
            assert (
                connection.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
                is True
            )
            with pytest.raises(DBAPIError):
                connection.execute(text("SELECT * FROM web_connections"))
        for bad_config in [
            app_config.model_copy(update={"tls_ca_file": None}),
            app_config.model_copy(
                update={
                    "database_url": SecretStr(
                        app_config.database_url.get_secret_value().replace("localhost", "127.0.0.1")
                    )
                }
            ),
        ]:
            with pytest.raises((DBAPIError, ssl.SSLCertVerificationError)):
                database_check(bad_config)
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num='obsolete-schema'"))
        assert not database_check(app_config)
    finally:
        if worker is not None:
            worker.dispose()
        if engine is not None:
            engine.dispose()
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def field_record():
    return json.loads(Path("research/saas/field-run.example.json").read_text())


def test_field_record_never_infers_import_accuracy_or_missing_costs():
    value = field_record()
    record = FieldRun.model_validate(value)
    result = observations(record)
    assert result["unrun_imports"] == 6 and not result["recorded_all_rows_exact"]
    assert result["allocated_total_usd"] is None
    value.update(
        expected_rows=12,
        extracted_rows=12,
        source_checked_rows=12,
        exact_rows=10,
        financial_reconciliation="passed",
        documents=2,
        physical_pages=4,
        source_review_seconds="120",
        support_minutes="3",
        labor_usd_per_hour="12.00",
        host_cost_usd="0.10",
        storage_cost_usd="0.20",
        provider_cost_usd="0.30",
        allocated_costs_confirmed=True,
    )
    result = observations(FieldRun.model_validate(value))
    assert not result["recorded_all_rows_exact"]
    assert Decimal(result["allocated_total_usd"]) == Decimal("1.60")
    assert Decimal(result["allocated_cost_per_document_usd"]) == Decimal("0.80")
    assert result["unrun_imports"] == 6


@pytest.mark.parametrize(
    "mutation",
    [
        "permission",
        "extra_private_data",
        "duplicates",
        "unobserved_pass",
        "false_count",
        "nan",
        "float_money",
        "bool_money",
    ],
)
def test_field_record_rejects_unsupported_claims(mutation):
    value = field_record()
    if mutation == "permission":
        value["data_kind"] = "permitted_field"
    elif mutation == "extra_private_data":
        value["account_number"] = "fictional-private"
    elif mutation == "duplicates":
        value["imports"][0]["output"] = "csv"
    elif mutation == "unobserved_pass":
        value["imports"][0]["status"] = "passed"
    elif mutation == "false_count":
        value["exact_rows"] = 1
    elif mutation == "float_money":
        value["host_cost_usd"] = 0.1
    elif mutation == "bool_money":
        value["labor_usd_per_hour"] = True
    else:
        value["host_cost_usd"] = "NaN"
    with pytest.raises(ValidationError):
        FieldRun.model_validate(value)


def test_private_cli_inputs_do_not_leak(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("saas_staging", "scripts/saas-staging.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "field.json"
    path.write_text(json.dumps(field_record()))
    path.chmod(0o644)
    monkeypatch.setattr("sys.argv", ["saas-staging.py", "validate-field-run", str(path)])
    assert module.main() == 2
    assert json.loads(capsys.readouterr().out)["code"] == "PRIVATE_INPUT_REQUIRED"
    path.chmod(0o600)
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid_record"
    path.write_text('{"account":"fictional-private-secret"}')
    assert module.main() == 2
    assert "fictional-private-secret" not in capsys.readouterr().out
    link = tmp_path / "link.json"
    link.symlink_to(path)
    assert not module.private_file(link)


def rehearsal_module(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "saas_rehearsal_test", "scripts/saas-rehearsal.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PRIVATE = tmp_path / "staging" / "rehearsal"
    module.VOLUME = "dockling-rehearsal-init-test-" + uuid4().hex
    return module


def test_rehearsal_init_preserves_material_and_isolates_config(tmp_path, monkeypatch):
    import hashlib

    module = rehearsal_module(tmp_path)
    module.initialize()
    before = {
        str(p.relative_to(module.PRIVATE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in module.PRIVATE.rglob("*")
        if p.is_file()
    }
    assert module.rehearsal_config().mode == "production"
    assert module.rehearsal_config(owner=True).mode == "production"
    assert (module.PRIVATE / "tls/server.key").stat().st_mode & 0o777 == 0o640
    assert (module.PRIVATE / "server.env").stat().st_mode & 0o777 == 0o600
    module.initialize()
    after = {
        str(p.relative_to(module.PRIVATE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in module.PRIVATE.rglob("*")
        if p.is_file()
    }
    assert before == after
    monkeypatch.setenv("STMTCONV_WEB_BASE_URL", "https://external.example.invalid")

    def forbidden(*_args):
        raise AssertionError("External configuration must fail before starting any containers")

    monkeypatch.setattr(module, "compose", forbidden)
    with pytest.raises(ValueError, match="cannot target"):
        module.setup()


def test_rehearsal_refuses_partial_or_unmatched_keys(tmp_path):
    module = rehearsal_module(tmp_path)
    module.initialize()
    key = module.PRIVATE / "ai-key.env"
    original = key.read_bytes()
    key.unlink()
    with pytest.raises(ValueError, match="Restore matched"):
        module.initialize()
    assert not key.exists()
    assert original


def test_observed_import_requires_all_values_and_expected_rows():
    value = field_record()
    value.update(expected_rows=2, extracted_rows=2, source_checked_rows=2, exact_rows=2)
    value["imports"][0].update(
        status="passed",
        destination_version="Synthetic destination 1",
        rows_imported=2,
        amounts_and_signs_checked=True,
        dates_checked=True,
        duplicate_behavior_checked=True,
    )
    result = observations(FieldRun.model_validate(value))
    assert result["passed_imports"] == 1 and result["unrun_imports"] == 5
    assert result["recorded_all_rows_exact"] and not result["automated_accuracy_certification"]
    value["imports"][0]["rows_imported"] = 1
    with pytest.raises(ValidationError):
        FieldRun.model_validate(value)


def test_host_staging_runner_requires_dedicated_paused_private_configuration(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("stage_server_test", "scripts/saas-server.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "server.env"
    data = (
        Path("config/staging-server.env.example")
        .read_text()
        .replace(
            "STMTCONV_WEB_ADMIN_SUBJECTS=[]", 'STMTCONV_WEB_ADMIN_SUBJECTS=["fictional-admin"]'
        )
    )
    path.write_text(data)
    path.chmod(0o600)
    key = tmp_path / "ai-key.env"
    key.write_text("STMTCONV_WEB_AI_ENCRYPTION_KEY=" + "a" * 64 + "\n")
    key.chmod(0o600)
    assert module.stage_config(path).mode == "production"
    monkeypatch.setenv("STMTCONV_WEB_AI_DISPATCH_ENABLED", "true")
    with pytest.raises(ValueError, match="dedicated staging"):
        module.stage_config(path)
    monkeypatch.delenv("STMTCONV_WEB_AI_DISPATCH_ENABLED")
    monkeypatch.setenv(
        "STMTCONV_WEB_DATABASE_URL",
        "postgresql+pg8000://dockling_app:fictional@localhost/production",
    )
    with pytest.raises(ValueError, match="dedicated staging"):
        module.stage_config(path)
