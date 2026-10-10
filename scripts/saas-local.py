"""Synthetic-only local services. Generated secrets never leave ignored .local-saas/."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LOCAL = ROOT / ".local-saas"
ISSUER = "http://127.0.0.1:8085/realms/dockling"


def stage_worker_models() -> None:
    """Mount only approved public artifacts, without widening the private source cache."""
    from stmtconv.model_setup import artifact_path, load_manifest, verify_artifacts

    source = ROOT / "models"
    target = LOCAL / "worker-models"
    manifest = load_manifest()
    verify_artifacts(source, manifest)
    if target.is_symlink():
        raise SystemExit("Worker model folder must not be a symlink.")
    target.mkdir(exist_ok=True, mode=0o755)
    target.chmod(0o755)
    approved = {artifact.path for artifact in manifest.files}
    for entry in target.rglob("*"):
        if entry.is_symlink() or (
            entry.is_file() and entry.relative_to(target).as_posix() not in approved
        ):
            raise SystemExit("Unexpected worker cache entry; use a clean worker-models folder.")
    for artifact in manifest.files:
        destination = artifact_path(target, artifact)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        for parent in [destination.parent, *destination.parent.parents]:
            if parent == target:
                break
            parent.chmod(0o755)
        try:
            verify_artifacts(target, manifest.model_copy(update={"files": [artifact]}))
        except Exception:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
            try:
                shutil.copyfile(artifact_path(source, artifact), temporary_path)
                temporary_path.chmod(0o644)
                temporary_path.replace(destination)
            finally:
                temporary_path.unlink(missing_ok=True)
        destination.chmod(0o644)
    verify_artifacts(target, manifest)
    print("Worker public model cache verified; original private model cache preserved.")


def write(name: str, value: str) -> None:
    path = LOCAL / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o644 if name in {"init.sql", "realm.json", "s3.json"} else 0o600)


def initialize() -> None:
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    LOCAL.chmod(0o700)
    if (LOCAL / "bootstrap.json").exists():
        print("Existing local credentials preserved.")
        worker_config()
        return
    found = subprocess.run(
        ["docker", "volume", "inspect", "dockling-saas_saas-postgres"],
        capture_output=True,
        check=False,
    )
    if found.returncode == 0:
        raise SystemExit(
            "Database volume exists without its credentials. Restore .local-saas from your backup; do not generate replacement passwords."
        )
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    keys = {
        name: secrets.token_hex(32)
        for name in [
            "postgres",
            "owner",
            "app",
            "worker",
            "keycloak",
            "identity_admin",
            "client",
            "session",
            "s3_access",
            "s3_secret",
        ]
    }
    users = []
    for username in [
        "owner-a",
        "editor-a",
        "viewer-a",
        "owner-b",
        "editor-b",
        "viewer-b",
        "operator",
    ]:
        users.append(
            {
                "id": str(uuid4()),
                "username": username,
                "email": username + "@example.test",
                "password": secrets.token_hex(12),
            }
        )
    data = {
        "keys": keys,
        "users": users,
        "workspaces": [str(uuid4()), str(uuid4())],
        "otp_secret": secrets.token_hex(20),
    }
    write("bootstrap.json", json.dumps(data, indent=2))
    write("postgres.env", "POSTGRES_PASSWORD=" + keys["postgres"] + "\n")
    sql = ""
    for role in ["owner", "app", "worker"]:
        sql += f"CREATE ROLE dockling_{role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{keys[role]}';\n"
    sql += "CREATE DATABASE dockling OWNER dockling_owner;\nCREATE DATABASE dockling_test OWNER dockling_owner;\n"
    sql += f"CREATE ROLE keycloak LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{keys['keycloak']}';\nCREATE DATABASE keycloak OWNER keycloak;\n"
    write("init.sql", sql)
    write(
        "keycloak.env",
        f"KC_DB_PASSWORD={keys['keycloak']}\nKC_BOOTSTRAP_ADMIN_USERNAME=local-admin\nKC_BOOTSTRAP_ADMIN_PASSWORD={keys['identity_admin']}\n",
    )
    realm_users = []
    for u in users:
        credentials = [{"type": "password", "value": u["password"], "temporary": False}]
        if u["username"] == "operator":
            credentials.append(
                {
                    "type": "otp",
                    "secretData": json.dumps({"value": data["otp_secret"]}),
                    "credentialData": json.dumps(
                        {
                            "subType": "totp",
                            "digits": 6,
                            "counter": 0,
                            "period": 30,
                            "algorithm": "HmacSHA1",
                        }
                    ),
                }
            )
        realm_users.append(
            {
                "id": u["id"],
                "username": u["username"],
                "email": u["email"],
                "emailVerified": True,
                "firstName": "Synthetic",
                "lastName": u["username"],
                "enabled": True,
                "credentials": credentials,
            }
        )
    realm = {
        "realm": "dockling",
        "enabled": True,
        "sslRequired": "none",
        "registrationAllowed": False,
        "bruteForceProtected": True,
        "users": realm_users,
        "clients": [
            {
                "clientId": "dockling-web",
                "enabled": True,
                "publicClient": False,
                "secret": keys["client"],
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "redirectUris": ["http://127.0.0.1:8000/auth/callback"],
                "webOrigins": ["http://127.0.0.1:8000"],
                "attributes": {"pkce.code.challenge.method": "S256"},
                "protocolMappers": [
                    {
                        "name": "verified authentication methods",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-amr-mapper",
                        "config": {"id.token.claim": "true", "access.token.claim": "false"},
                    }
                ],
            }
        ],
        "browserFlow": "foundation-browser",
        "authenticatorConfig": [
            {
                "alias": "otp-reference",
                "config": {"default.reference.value": "otp", "default.reference.maxAge": "300"},
            }
        ],
        "authenticationFlows": [
            {
                "alias": "foundation-browser",
                "providerId": "basic-flow",
                "topLevel": True,
                "builtIn": False,
                "authenticationExecutions": [
                    {
                        "authenticator": "auth-username-password-form",
                        "requirement": "REQUIRED",
                        "priority": 10,
                        "authenticatorFlow": False,
                    },
                    {
                        "flowAlias": "foundation-otp",
                        "requirement": "CONDITIONAL",
                        "priority": 20,
                        "authenticatorFlow": True,
                    },
                ],
            },
            {
                "alias": "foundation-otp",
                "providerId": "basic-flow",
                "topLevel": False,
                "builtIn": False,
                "authenticationExecutions": [
                    {
                        "authenticator": "conditional-user-configured",
                        "requirement": "REQUIRED",
                        "priority": 10,
                        "authenticatorFlow": False,
                    },
                    {
                        "authenticator": "auth-otp-form",
                        "authenticatorConfig": "otp-reference",
                        "requirement": "REQUIRED",
                        "priority": 20,
                        "authenticatorFlow": False,
                    },
                ],
            },
        ],
    }
    write("realm.json", json.dumps(realm, indent=2))
    write(
        "s3.json",
        json.dumps(
            {
                "identities": [
                    {
                        "name": "dockling",
                        "credentials": [
                            {"accessKey": keys["s3_access"], "secretKey": keys["s3_secret"]}
                        ],
                        "actions": ["Admin", "Read", "Write", "List", "Tagging"],
                    }
                ]
            }
        ),
    )
    fields = {
        "MODE": "local",
        "DATABASE_URL": f"postgresql+pg8000://dockling_app:{keys['app']}@127.0.0.1:55432/dockling",
        "SESSION_KEY": keys["session"],
        "BASE_URL": "http://127.0.0.1:8000",
        "OIDC_ISSUER": ISSUER,
        "OIDC_CLIENT_ID": "dockling-web",
        "OIDC_CLIENT_SECRET": keys["client"],
        "ADMIN_SUBJECTS": json.dumps([users[-1]["id"]]),
        "S3_ENDPOINT": "http://127.0.0.1:8333",
        "S3_ACCESS_KEY": keys["s3_access"],
        "S3_SECRET_KEY": keys["s3_secret"],
    }
    write("server.env", "".join("STMTCONV_WEB_" + k + "=" + v + "\n" for k, v in fields.items()))
    fields["DATABASE_URL"] = (
        f"postgresql+pg8000://dockling_owner:{keys['owner']}@127.0.0.1:55432/dockling"
    )
    write("migrate.env", "".join("STMTCONV_WEB_" + k + "=" + v + "\n" for k, v in fields.items()))
    print(
        "Created synthetic credentials in ignored .local-saas/bootstrap.json. Do not upload this folder."
    )
    worker_config()


def worker_config() -> None:
    """Add the restricted worker identity without replacing existing private settings."""
    data = json.loads((LOCAL / "bootstrap.json").read_text())
    broker = LOCAL / "broker"
    broker.mkdir(exist_ok=True, mode=0o711)
    password = data["keys"]["worker"]
    write(
        "worker.env",
        f"STMTCONV_WORKER_DATABASE_URL=postgresql+pg8000://dockling_worker:{password}@postgres:5432/dockling\n",
    )


def compose(action: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.saas.yaml",
            action,
            *(["-d"] if action == "up" else []),
        ],
        cwd=ROOT,
        check=True,
    )


def readiness() -> None:
    from sqlalchemy import text

    from stmtconv.config import load_hosted_settings
    from stmtconv.web.database import database
    from stmtconv.web.storage import ObjectStore

    cfg = load_hosted_settings(LOCAL / "server.env")
    for attempt in range(90):
        try:
            with urllib.request.urlopen(
                ISSUER + "/.well-known/openid-configuration", timeout=3
            ) as r:
                assert json.load(r)["issuer"] == ISSUER
            with database(cfg).connect() as conn:
                conn.execute(text("SELECT 1"))
            ObjectStore(cfg).probe()
            print("Identity, PostgreSQL and authenticated private storage are ready.")
            return
        except Exception:
            if attempt == 89:
                raise SystemExit(
                    "Services did not become ready. Check docker compose -f compose.saas.yaml ps and local container logs; redact credentials before sharing."
                ) from None
            time.sleep(1)


def seed() -> None:
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from stmtconv.config import load_hosted_settings
    from stmtconv.web.database import database
    from stmtconv.web.models import Membership, User, Workspace

    data = json.loads((LOCAL / "bootstrap.json").read_text())
    with Session(database(load_hosted_settings(LOCAL / "migrate.env"))) as db, db.begin():
        for i, wid in enumerate(data["workspaces"]):
            if not db.get(Workspace, UUID(wid)):
                db.add(Workspace(id=UUID(wid), name="Sample workspace " + ("A" if i == 0 else "B")))
        db.flush()
        for u in data["users"]:
            user = db.scalar(select(User).where(User.issuer == ISSUER, User.subject == u["id"]))
            if user is None:
                user = User(issuer=ISSUER, subject=u["id"], email=u["email"], email_verified=True)
                db.add(user)
                db.flush()
            if u["username"] == "operator":
                continue
            wid = UUID(data["workspaces"][0 if u["username"].endswith("-a") else 1])
            if (
                db.scalar(
                    select(Membership).where(
                        Membership.workspace_id == wid, Membership.user_id == user.id
                    )
                )
                is None
            ):
                db.add(
                    Membership(workspace_id=wid, user_id=user.id, role=u["username"].split("-")[0])
                )
    print("Two synthetic workspaces and owner/editor/viewer memberships are ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "init",
            "up",
            "setup",
            "down",
            "check",
            "run",
            "migrate",
            "worker",
            "worker-build",
            "reap",
        ],
    )
    args = parser.parse_args()
    if args.command in {"init", "up", "setup"}:
        initialize()
    if args.command in {"up", "setup"}:
        compose("up")
    if args.command in {"setup", "check"}:
        readiness()
    if args.command in {"setup", "migrate"}:
        from stmtconv.config import load_hosted_settings
        from stmtconv.web.database import migrate

        migrate(load_hosted_settings(LOCAL / "migrate.env"))
    if args.command == "setup":
        seed()
    if args.command == "down":
        subprocess.run(
            ["docker", "compose", "--profile", "conversion", "-f", "compose.saas.yaml", "down"],
            cwd=ROOT,
            check=True,
        )
        print("Services stopped; volumes and credentials preserved.")
    if args.command == "run":
        import uvicorn

        from stmtconv.config import load_hosted_settings
        from stmtconv.web.app import create_app

        app = create_app(load_hosted_settings(LOCAL / "server.env"))
        app.state.broker.start(LOCAL / "broker" / "socket")
        try:
            uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
        finally:
            app.state.broker.close()
    if args.command == "worker-build":
        # Verified binary wheels are installed before copying this development-only environment.
        subprocess.run(["bash", "scripts/install-saas-linux.sh"], cwd=ROOT, check=True)
        if Path(sys.prefix) != ROOT / ".venv":
            # A fresh clone can start with system Python; model/build helpers need the locked venv.
            subprocess.run(
                [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker-build"],
                cwd=ROOT,
                check=True,
            )
            return
        from stmtconv.config import load_settings
        from stmtconv.model_setup import download, load_manifest, verify_artifacts

        settings = load_settings()
        try:
            verify_artifacts(ROOT / "models", load_manifest())
        except Exception:
            download(settings)
        stage_worker_models()
        from stmtconv.config import build_certificate_bundle

        build = LOCAL / "build"
        build.mkdir(exist_ok=True, mode=0o700)
        (build / "ca-certificates.crt").write_bytes(build_certificate_bundle().read_bytes())
        subprocess.run(
            [
                "docker",
                "--config",
                str(LOCAL / "docker"),
                "build",
                "--network=host",
                "--build-arg",
                "HTTP_PROXY",
                "--build-arg",
                "HTTPS_PROXY",
                "-f",
                "Dockerfile.worker",
                "-t",
                "dockling-worker:phase2",
                ".",
            ],
            cwd=ROOT,
            check=True,
        )
    if args.command == "worker":
        worker_config()
        stage_worker_models()
        subprocess.run(
            [
                "docker",
                "compose",
                "--profile",
                "conversion",
                "-f",
                "compose.saas.yaml",
                "up",
                "-d",
                "worker",
            ],
            cwd=ROOT,
            check=True,
        )
    if args.command == "reap":
        from stmtconv.config import load_hosted_settings
        from stmtconv.web.database import PostgresUnitOfWork, database
        from stmtconv.web.maintenance import reap
        from stmtconv.web.storage import ObjectStore

        config = load_hosted_settings(LOCAL / "server.env")
        checkpoint = LOCAL / "reap-cursors.json"
        cursors = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        try:
            counts, cursors = reap(
                ObjectStore(config), PostgresUnitOfWork(database(config)), cursors
            )
        except Exception:
            raise SystemExit(
                "Cleanup could not finish. No complete deletion is claimed; retry this pass."
            ) from None
        write("reap-cursors.json", json.dumps(cursors))
        print(
            f"Cleanup pass: {counts['examined']} examined, {counts['deleted']} abandoned objects removed. Active source documents are preserved."
        )


if __name__ == "__main__":
    main()
