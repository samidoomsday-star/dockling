"""Real PostgreSQL/S3 tests; generated sessions exist only in this test fixture."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stmtconv.config import load_hosted_settings
from stmtconv.web.app import create_app
from stmtconv.web.auth import csrf, digest
from stmtconv.web.database import database, migrate
from stmtconv.web.models import Base, Membership, User, WebSession, Workspace
from stmtconv.web.storage import ObjectStore


@pytest.fixture(scope="session")
def configs():
    config = load_hosted_settings()
    admin = load_hosted_settings(Path(".local-saas/migrate.env"))
    config = config.model_copy(
        update={
            "s3_bucket": config.s3_bucket + "-test",
            "database_url": SecretStr(
                config.database_url.get_secret_value().rsplit("/", 1)[0] + "/dockling_test"
            ),
        }
    )
    admin = admin.model_copy(
        update={
            "database_url": SecretStr(
                admin.database_url.get_secret_value().rsplit("/", 1)[0] + "/dockling_test"
            )
        }
    )
    migrate(admin)
    ObjectStore(config).ensure_bucket()
    yield config, admin


@pytest.fixture
def world(configs):
    config, admin = configs
    owner_engine = database(admin)
    with Session(owner_engine) as db, db.begin():
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        ws = [Workspace(name="Synthetic A"), Workspace(name="Synthetic B")]
        db.add_all(ws)
        db.flush()
        users = {}
        creds = {}
        for space in range(2):
            for role in ["owner", "editor", "viewer"]:
                name = role + str(space)
                u = User(
                    issuer=config.oidc_issuer,
                    subject=str(uuid4()),
                    email=name + "@example.test",
                    email_verified=True,
                )
                db.add(u)
                db.flush()
                db.add(Membership(workspace_id=ws[space].id, user_id=u.id, role=role))
                users[name] = u.id
                token = str(uuid4())
                s = WebSession(
                    token_hash=digest(token),
                    user_id=u.id,
                    workspace_id=ws[space].id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    mfa=False,
                )
                db.add(s)
                creds[name] = {"cookie": token, "csrf": csrf(config, s)}
        for name, mfa in [("admin", True), ("admin-no-mfa", False), ("outsider", False)]:
            sub = config.admin_subjects[0] if name.startswith("admin") else str(uuid4())
            if name == "admin-no-mfa":
                u = db.scalar(select(User).where(User.subject == sub))
                assert u
            else:
                u = User(
                    issuer=config.oidc_issuer,
                    subject=sub,
                    email=name + "@example.test",
                    email_verified=True,
                )
                db.add(u)
                db.flush()
            users[name] = u.id
            token = str(uuid4())
            s = WebSession(
                token_hash=digest(token),
                user_id=u.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                mfa=mfa,
                mfa_until=datetime.now(UTC) + timedelta(minutes=5) if mfa else None,
            )
            db.add(s)
            creds[name] = {"cookie": token, "csrf": csrf(config, s)}
        ids = [w.id for w in ws]
    app = create_app(config)

    def client(name):
        c = TestClient(app, base_url=config.base_url)
        c.cookies.set("dockling_session", creds[name]["cookie"])
        c.headers.update(
            {
                "Origin": config.base_url,
                "X-CSRF-Token": creds[name]["csrf"],
                "Idempotency-Key": str(uuid4()),
            }
        )
        return c

    yield {
        "config": config,
        "admin": admin,
        "engine": owner_engine,
        "app": app,
        "client": client,
        "users": users,
        "workspaces": ids,
        "creds": creds,
    }
    app.state.engine.dispose()
    owner_engine.dispose()


@pytest.fixture
def store(configs):
    store = ObjectStore(configs[0])
    store.ensure_bucket()
    return store


def validate_response(name, value):
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    contract = yaml.safe_load(Path("contracts/saas/openapi.yaml").read_text())
    registry = Registry().with_resource(
        "urn:dockling:api", Resource.from_contents(contract, default_specification=DRAFT202012)
    )
    Draft202012Validator(
        {"$ref": "urn:dockling:api#/components/schemas/" + name},
        registry=registry,
        format_checker=FormatChecker(),
    ).validate(value)
