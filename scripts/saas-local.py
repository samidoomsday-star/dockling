"""Synthetic-only local services. Generated secrets never leave ignored .local-saas/."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LOCAL = ROOT / ".local-saas"
ISSUER = "http://127.0.0.1:8085/realms/dockling"


def write(name: str, value: str) -> None:
    path = LOCAL / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o644 if name in {"init.sql", "realm.json", "s3.json"} else 0o600)


def initialize() -> None:
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    LOCAL.chmod(0o700)
    if (LOCAL / "bootstrap.json").exists():
        print("Existing local credentials preserved.")
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
        "command", choices=["init", "up", "setup", "down", "check", "run", "migrate"]
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
        compose("down")
        print("Services stopped; volumes and credentials preserved.")
    if args.command == "run":
        import uvicorn

        from stmtconv.config import load_hosted_settings
        from stmtconv.web.app import create_app

        uvicorn.run(
            create_app(load_hosted_settings(LOCAL / "server.env")),
            host="127.0.0.1",
            port=8000,
            access_log=False,
        )


if __name__ == "__main__":
    main()
