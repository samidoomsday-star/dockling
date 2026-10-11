"""Isolated loopback HTTPS rehearsal; never deploys publicly or resets local data."""

import argparse
import importlib.util
import json
import os
import secrets
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings, load_hosted_settings
from stmtconv.web.database import database, migrate
from stmtconv.web.models import (
    BillingEvidence,
    BillingInvoice,
    CommercialPlan,
    Entitlement,
    Membership,
    User,
    Workspace,
    now,
)
from stmtconv.web.staging import preflight, report_json
from stmtconv.web.storage import ObjectStore
from stmtconv.web.tls import service_tls

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".staging-saas" / "rehearsal"
ORIGIN = "https://localhost:8443"
ISSUER = "https://localhost:8444/realms/dockling"
VOLUME = "dockling-staging-rehearsal_staging-postgres"


def fixture_helper():
    spec = importlib.util.spec_from_file_location(
        "rehearsal_fixture", ROOT / "scripts/saas-local.py"
    )
    assert spec and spec.loader
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.LOCAL = PRIVATE
    helper.ISSUER = ISSUER
    return helper


def write(name: str, content: str) -> None:
    path = PRIVATE / name
    if path.is_symlink() or path.exists():
        raise ValueError("Existing rehearsal material requires inspection")
    with path.open("x") as output:
        path.chmod(0o600)
        output.write(content)


def certificates() -> None:
    directory = PRIVATE / "tls"
    # Public certs and a group-readable leaf key; only the identity's explicit group can read it.
    directory.mkdir(mode=0o755)
    # mkdir's requested mode is reduced by a private host umask. PostgreSQL
    # and Keycloak use different UIDs and must traverse this mounted directory.
    directory.chmod(0o755)
    at = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Dockling loopback rehearsal CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(at - timedelta(minutes=5))
        .not_valid_after(at + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.NameConstraints(
                permitted_subtrees=[x509.DNSName("localhost"), x509.DNSName("postgres")],
                excluded_subtrees=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(at - timedelta(minutes=5))
        .not_valid_after(at + timedelta(days=7))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.DNSName("postgres")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    for file, content, mode in [
        ("tls/ca.pem", ca.public_bytes(serialization.Encoding.PEM), 0o644),
        ("tls/server.pem", certificate.public_bytes(serialization.Encoding.PEM), 0o644),
        (
            "tls/server.key",
            leaf_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o640,
        ),
    ]:
        path = PRIVATE / file
        with path.open("xb") as output:
            path.chmod(mode)
            output.write(content)
    # No signing key is retained. This CA cannot issue later certificates here.


def initialize() -> None:
    parent = PRIVATE.parent
    if parent.is_symlink() or PRIVATE.is_symlink():
        raise ValueError("Private directories must not be symlinks")
    parent.mkdir(exist_ok=True, mode=0o700)
    marker = PRIVATE / "rehearsal.json"
    if marker.is_file():
        if json.loads(marker.read_text()) != {"scope": "synthetic_loopback_only", "version": 1}:
            raise ValueError("Unexpected rehearsal scope")
        for name in [
            "bootstrap.json",
            "server.env",
            "migrate.env",
            "worker.env",
            "ai-key.env",
            "compose.env",
            "tls/server.key",
            "tls/ca.pem",
            "tls/server.pem",
        ]:
            path = PRIVATE / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Restore matched rehearsal material; do not replace keys")
        print("Existing rehearsal configuration and keys preserved.")
        return
    if PRIVATE.exists():
        raise ValueError("Incomplete rehearsal directory requires inspection before continuing")
    helper = fixture_helper()
    helper.initialize(VOLUME)
    certificates()
    data = json.loads((PRIVATE / "bootstrap.json").read_text())
    keys = data["keys"]
    realm_path = PRIVATE / "realm.json"
    realm = json.loads(realm_path.read_text())
    realm["sslRequired"] = "all"
    client = realm["clients"][0]
    client["redirectUris"] = [ORIGIN + "/auth/callback"]
    client["webOrigins"] = [ORIGIN]
    helper.write("realm.json", json.dumps(realm, indent=2))
    fields = {
        "MODE": "production",
        "AI_DISPATCH_ENABLED": "false",
        "DATABASE_URL": f"postgresql+pg8000://dockling_app:{keys['app']}@localhost:55433/dockling",
        "SESSION_KEY": keys["session"],
        "BASE_URL": ORIGIN,
        "OIDC_ISSUER": ISSUER,
        "OIDC_CLIENT_ID": "dockling-web",
        "OIDC_CLIENT_SECRET": keys["client"],
        "ADMIN_SUBJECTS": json.dumps([data["users"][-1]["id"]]),
        "S3_ENDPOINT": "https://localhost:8445",
        "S3_ACCESS_KEY": keys["s3_access"],
        "S3_SECRET_KEY": keys["s3_secret"],
        "TLS_CA_FILE": str(PRIVATE / "tls/ca.pem"),
    }
    helper.write(
        "server.env", "".join("STMTCONV_WEB_" + k + "=" + v + "\n" for k, v in fields.items())
    )
    fields["DATABASE_URL"] = (
        f"postgresql+pg8000://dockling_owner:{keys['owner']}@localhost:55433/dockling"
    )
    helper.write(
        "migrate.env", "".join("STMTCONV_WEB_" + k + "=" + v + "\n" for k, v in fields.items())
    )
    helper.write(
        "worker.env",
        "STMTCONV_WORKER_MODE=production\nSTMTCONV_WORKER_TLS_CA_FILE=/private/ca.pem\n"
        + f"STMTCONV_WORKER_DATABASE_URL=postgresql+pg8000://dockling_worker:{keys['worker']}@postgres:5432/dockling\n",
    )
    write("ai-key.env", "STMTCONV_WEB_AI_ENCRYPTION_KEY=" + secrets.token_hex(32) + "\n")
    write("compose.env", "DOCKLING_REHEARSAL_GID=" + str(os.getgid()) + "\n")
    write("rehearsal.json", json.dumps({"scope": "synthetic_loopback_only", "version": 1}))
    print("Independent synthetic HTTPS configuration created; local volumes and keys untouched.")


def compose(*arguments: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(PRIVATE / "compose.env"),
            "--profile",
            "conversion",
            "-f",
            "compose.staging-rehearsal.yaml",
            *arguments,
        ],
        cwd=ROOT,
        check=True,
    )


def rehearsal_config(*, owner: bool = False) -> HostedSettings:
    config = load_hosted_settings(PRIVATE / ("migrate.env" if owner else "server.env"))
    parsed = urlsplit(config.database_url.get_secret_value())
    if (
        config.mode != "production"
        or config.base_url != ORIGIN
        or config.oidc_issuer != ISSUER
        or config.s3_endpoint != "https://localhost:8445"
        or config.s3_bucket != "dockling-private"
        or parsed.hostname != "localhost"
        or parsed.port != 55433
        or parsed.path != "/dockling"
        or parsed.username != ("dockling_owner" if owner else "dockling_app")
        or parsed.query
        or parsed.fragment
        or config.tls_ca_file != PRIVATE / "tls/ca.pem"
        or config.ai_dispatch_enabled
        or config.commercial_offers_enabled
    ):
        raise ValueError(
            "Rehearsal settings cannot target an external or local development service"
        )
    return config


def setup() -> None:
    initialize()
    config = rehearsal_config()
    admin = rehearsal_config(owner=True)
    compose("up", "-d", "postgres", "identity", "storage")
    deadline = time.monotonic() + 180
    last_failure: tuple[str, str] | None = None
    while time.monotonic() < deadline:
        engine = database(admin)
        stage = "DATABASE_TLS"
        try:
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                    )
                    is True
                )
            stage = "IDENTITY_TLS"
            with httpx.Client(verify=service_tls(config), timeout=5, trust_env=False) as client:
                response = client.get(ISSUER + "/.well-known/openid-configuration")
                assert response.status_code == 200 and response.json()["issuer"] == ISSUER
            stage = "PRIVATE_STORAGE_TLS"
            store = ObjectStore(config)
            store.probe()
            break
        except Exception as error:
            failure = (stage, type(error).__name__)
            if failure != last_failure:
                # Class names and fixed stages only; never exception arguments, URLs or keys.
                print(
                    json.dumps({"status": "waiting", "check": stage, "error_type": failure[1]}),
                    flush=True,
                )
                last_failure = failure
            time.sleep(1)
        finally:
            engine.dispose()
    else:
        raise ValueError("Verified rehearsal service readiness exceeded its deadline")
    migrate(admin)
    fixture_helper().seed()
    seed_entitlements()
    compose("up", "-d", "worker")
    print("Production-mode TLS services, synthetic memberships and worker started.")


def seed_entitlements(workspaces: list[str] | None = None) -> None:
    data = json.loads((PRIVATE / "bootstrap.json").read_text())
    engine = database(rehearsal_config(owner=True))
    try:
        with Session(engine) as db, db.begin():
            actor = db.scalar(
                select(User).where(User.issuer == ISSUER, User.subject == data["users"][-1]["id"])
            )
            assert actor
            for wid in workspaces if workspaces is not None else data["workspaces"]:
                workspace = UUID(wid)
                if db.get(Entitlement, workspace) is not None:
                    continue
                plan = CommercialPlan(
                    actor_id=actor.id,
                    data={
                        "name": "Fictional HTTPS rehearsal",
                        "pages_per_month": 500,
                        "seats": 10,
                        "monthly_amount": "0.00",
                        "currency": "USD",
                        "approved_for_customers": False,
                    },
                )
                db.add(plan)
                db.flush()
                invoice = BillingInvoice(
                    workspace_id=workspace,
                    plan_id=plan.id,
                    status="paid",
                    version=1,
                    valid_until=now() + timedelta(days=7),
                )
                db.add(invoice)
                db.flush()
                db.add(
                    BillingEvidence(
                        workspace_id=workspace,
                        invoice_id=invoice.id,
                        actor_id=actor.id,
                        version=1,
                        status="paid",
                        reference="fictional-https-rehearsal-" + wid,
                    )
                )
                db.add(
                    Entitlement(
                        workspace_id=workspace,
                        invoice_id=invoice.id,
                        status="active",
                        valid_until=invoice.valid_until,
                        limits={"pages_per_month": 500, "seats": 10},
                    )
                )
    finally:
        engine.dispose()


def verification_workspaces() -> list[str]:
    """New fictional test scopes; never reset prior pages, invoices, jobs or customers."""
    data = json.loads((PRIVATE / "bootstrap.json").read_text())
    engine = database(rehearsal_config(owner=True))
    identifiers = []
    try:
        with Session(engine) as db, db.begin():
            for suffix in ["-a", "-b"]:
                workspace = Workspace(name="Fictional HTTPS verification")
                db.add(workspace)
                db.flush()
                identifiers.append(str(workspace.id))
                for entry in data["users"]:
                    if not entry["username"].endswith(suffix):
                        continue
                    user = db.scalar(
                        select(User).where(User.issuer == ISSUER, User.subject == entry["id"])
                    )
                    if not user or not user.email or not user.email.endswith("@example.test"):
                        raise ValueError("Only known fictional identities may enter the rehearsal")
                    db.add(
                        Membership(
                            workspace_id=workspace.id,
                            user_id=user.id,
                            role=entry["username"].split("-")[0],
                        )
                    )
    finally:
        engine.dispose()
    seed_entitlements(identifiers)
    return identifiers


def run() -> None:
    import uvicorn

    from stmtconv.web.app import create_app

    initialize()
    config = rehearsal_config()
    app = create_app(config)
    app.state.broker.start(PRIVATE / "broker/socket")
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8443,
            access_log=False,
            proxy_headers=False,
            ssl_certfile=str(PRIVATE / "tls/server.pem"),
            ssl_keyfile=str(PRIVATE / "tls/server.key"),
        )
    finally:
        app.state.broker.close()
        app.state.engine.dispose()


def wait_ready() -> None:
    """Bound startup polling; full security preflight still runs separately once."""
    config = rehearsal_config()
    deadline = time.monotonic() + 120
    with httpx.Client(verify=service_tls(config), timeout=5, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(ORIGIN + "/api/v1/health/ready")
                if response.status_code == 200 and response.json().get("status") == "ready":
                    print(json.dumps({"status": "ready", "code": "HTTPS_API_READY"}))
                    return
            except Exception:
                pass
            time.sleep(1)
    raise ValueError("Verified HTTPS startup exceeded its deadline")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["init", "setup", "run", "wait-ready", "check", "stop", "verification-workspaces"],
    )
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize()
        elif args.command == "setup":
            setup()
        elif args.command == "run":
            run()
        elif args.command == "wait-ready":
            wait_ready()
        elif args.command == "verification-workspaces":
            print(json.dumps(verification_workspaces()))
        elif args.command == "stop":
            compose("stop")
            print("Rehearsal containers stopped; all volumes and private keys preserved.")
        elif args.command == "check":
            result = preflight(rehearsal_config())
            print(report_json(result))
            return 0 if result.status == "passed" else 2
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "code": "REHEARSAL_CHECK_REQUIRED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
