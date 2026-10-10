"""Isolation and security against real PostgreSQL and private S3, not SQLite."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from conftest import validate_response
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from stmtconv.errors import StmtconvError
from stmtconv.orders import store as local_store
from stmtconv.orders.metadata import LocalMetadata
from stmtconv.web.database import database, migrate
from stmtconv.web.errors import WebError
from stmtconv.web.models import Artifact, Membership, User, WebSession
from stmtconv.web.repository import HostedMetadata

BODY = {
    "name": "Synthetic job",
    "currency": "USD",
    "date_order": "auto",
    "outputs": ["excel", "csv"],
}


def create(world, name="owner0", body=None):
    c = world["client"](name)
    r = c.post("/api/v1/jobs", json=body or BODY)
    assert r.status_code == 201, r.text
    validate_response("Job", r.json())
    return r.json()


@pytest.mark.parametrize("name", ["owner0", "editor0", "viewer0", "owner1", "editor1", "viewer1"])
def test_session_and_workspace_contract(world, name):
    c = world["client"](name)
    r = c.get("/api/v1/session")
    assert r.status_code == 200
    validate_response("Session", r.json())
    assert r.json()["role"] == name[:-1]
    work = c.get("/api/v1/workspaces")
    validate_response("WorkspaceList", work.json())
    assert len(work.json()["items"]) == 1
    other = world["workspaces"][1 - int(name[-1])]
    assert c.post("/api/v1/session/workspace", json={"workspace_id": str(other)}).status_code == 404


@pytest.mark.parametrize("name", ["owner0", "editor0", "viewer0", "admin"])
def test_cross_tenant_ids_lists_and_children(world, name):
    job = create(world, "owner1")
    c = world["client"](name)
    assert c.get("/api/v1/jobs/" + job["id"]).status_code == 404
    assert c.get("/api/v1/jobs/" + job["id"] + "/activity").status_code == 404
    result = c.get("/api/v1/jobs")
    if name == "admin":
        assert result.status_code == 404
    else:
        assert result.json()["items"] == []
        validate_response("JobList", result.json())
    # Intake is implemented in Phase 2; a complete command exercises its authorization.
    result = c.post("/api/v1/jobs/" + job["id"] + "/intake", json={"expected_revision": 1})
    assert result.status_code == (403 if name == "viewer0" else 404)


def test_roles_boundaries_and_safe_errors(world):
    owner = world["client"]("owner0")
    editor = world["client"]("editor0")
    viewer = world["client"]("viewer0")
    assert viewer.post("/api/v1/jobs", json=BODY).status_code == 403
    for c in [editor, viewer]:
        assert c.get("/api/v1/members").status_code == 403
        assert (
            c.post(
                "/api/v1/invitations", json={"email": "outsider@example.test", "role": "viewer"}
            ).status_code
            == 403
        )
    for c in [owner, editor, viewer, world["client"]("admin-no-mfa")]:
        assert c.get("/api/v1/admin/health").status_code == 403
    health = world["client"]("admin").get("/api/v1/admin/health")
    assert health.status_code == 200
    validate_response("Health", health.json())
    assert health.json()["worker"] == "unknown"
    r = owner.post(
        "/api/v1/jobs", json={**BODY, "role": "owner", "api_key": "SYNTHETIC_DO_NOT_ECHO"}
    )
    assert r.status_code == 422 and "SYNTHETIC_DO_NOT_ECHO" not in r.text
    validate_response("Error", r.json())
    assert owner.post("/api/v1/jobs", content=b"x" * 65537).status_code == 413
    assert owner.get("/api/v1/jobs?limit=101").status_code == 422
    assert owner.post("/api/v1/jobs", json={**BODY, "outputs": ["csv", "csv"]}).status_code == 422
    assert owner.get("/api/v1/jobs?cursor=forged").status_code == 400


def test_csrf_logout_expiry_and_revocation(world):
    c = world["client"]("editor0")
    token = c.get("/api/v1/session").json()["csrf_token"]
    c.get("/api/v1/settings")
    assert token == c.get("/api/v1/session").json()["csrf_token"]
    for header in [{"X-CSRF-Token": "forged"}, {"Origin": "https://untrusted.example"}]:
        assert c.post("/api/v1/jobs", json=BODY, headers=header).status_code == 403
    assert c.post("/api/v1/session/logout").status_code == 204
    assert c.get("/api/v1/session").status_code == 401
    expired = world["client"]("viewer0")
    with Session(world["engine"]) as db, db.begin():
        s = db.scalar(select(WebSession).where(WebSession.user_id == world["users"]["viewer0"]))
        s.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert expired.get("/api/v1/session").status_code == 401
    editor = world["client"]("editor1")
    with Session(world["engine"]) as db, db.begin():
        m = db.scalar(select(Membership).where(Membership.user_id == world["users"]["editor1"]))
        m.active = False
    assert editor.get("/api/v1/session").json()["role"] is None
    assert editor.post("/api/v1/jobs", json=BODY).status_code == 404
    assert (
        world["client"]("owner0").get("/auth/callback?state=forged&code=secret").status_code == 401
    )


def test_concurrent_idempotency_and_payload_conflict(world):
    def send(_):
        c = world["client"]("owner0")
        return c.post("/api/v1/jobs", json=BODY, headers={"Idempotency-Key": "repeat-job"})

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(send, range(12)))
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    c = world["client"]("owner0")
    assert len(c.get("/api/v1/jobs").json()["items"]) == 1
    assert (
        c.post(
            "/api/v1/jobs",
            json={**BODY, "name": "Changed"},
            headers={"Idempotency-Key": "repeat-job"},
        ).status_code
        == 409
    )
    job = responses[0].json()
    a = c.get("/api/v1/jobs/" + job["id"] + "/activity")
    validate_response("EventList", a.json())
    assert len(a.json()["items"]) == 1


def test_cursor_scope_final_owner_and_expected_version(world):
    create(world)
    create(world)
    c = world["client"]("owner0")
    page = c.get("/api/v1/jobs?limit=1").json()
    assert page["next_cursor"]
    second = c.get("/api/v1/jobs", params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert page["items"][0]["id"] != second["items"][0]["id"]
    assert (
        world["client"]("owner1")
        .get("/api/v1/jobs", params={"cursor": page["next_cursor"]})
        .status_code
        == 400
    )
    members = c.get("/api/v1/members").json()
    validate_response("MemberList", members)
    owner = next(m for m in members["items"] if m["role"] == "owner")
    url = "/api/v1/members/" + owner["id"]
    assert (
        c.patch(url, json={"expected_version": owner["version"], "active": False}).status_code
        == 409
    )
    assert c.patch(url, json={"expected_version": 999, "role": "editor"}).status_code == 409
    editor = next(m for m in members["items"] if m["role"] == "editor")
    new = c.patch(
        "/api/v1/members/" + editor["id"],
        json={"expected_version": editor["version"], "role": "owner"},
    )
    assert new.status_code == 200
    validate_response("Member", new.json())
    assert (
        c.patch(
            url,
            json={"expected_version": owner["version"], "active": False},
            headers={"Idempotency-Key": "revoke-owner"},
        ).status_code
        == 200
    )
    assert c.get("/api/v1/jobs").status_code == 404


def test_invitations_verified_email_single_use_and_revoke(world):
    c = world["client"]("owner0")
    r = c.post("/api/v1/invitations", json={"email": "outsider@example.test", "role": "viewer"})
    assert r.status_code == 201
    validate_response("InvitationDelivery", r.json())
    token = r.json()["accept_url"].split("#")[1]
    outsider = world["client"]("outsider")
    assert (
        world["client"]("owner1")
        .post("/api/v1/invitations/accept", json={"token": token})
        .status_code
        == 404
    )
    accepted = outsider.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers={"Idempotency-Key": "accept-once"},
    )
    assert accepted.status_code == 200
    validate_response("Workspace", accepted.json())
    assert (
        outsider.post(
            "/api/v1/invitations/accept",
            json={"token": token},
            headers={"Idempotency-Key": "accept-once"},
        ).status_code
        == 200
    )
    assert (
        outsider.post(
            "/api/v1/invitations/accept",
            json={"token": token},
            headers={"Idempotency-Key": "another"},
        ).status_code
        == 404
    )
    assert outsider.get("/api/v1/session").json()["role"] == "viewer"
    r = c.post(
        "/api/v1/invitations",
        json={"email": "editor1@example.test", "role": "editor"},
        headers={"Idempotency-Key": "second"},
    )
    token = r.json()["accept_url"].split("#")[1]
    assert (
        c.delete(
            "/api/v1/invitations/" + r.json()["id"], headers={"Idempotency-Key": "revoke"}
        ).status_code
        == 204
    )
    assert (
        world["client"]("editor1")
        .post("/api/v1/invitations/accept", json={"token": token})
        .status_code
        == 404
    )


def test_database_roles_composite_fk_and_private_artifacts(world, store):
    a = create(world)
    b = create(world, "owner1")
    config = world["config"]
    runtime = database(config)
    with runtime.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar() == "dockling_app"
        with pytest.raises(ProgrammingError):
            conn.execute(text("CREATE TABLE forbidden (id integer)"))
    bad = Artifact(
        workspace_id=world["workspaces"][0],
        job_id=b["id"],
        object_key=str(uuid4()),
        sha256="0" * 64,
        revision=1,
        kind="synthetic",
        bytes=1,
    )
    with Session(world["engine"]) as db:
        db.add(bad)
        with pytest.raises(ProgrammingError) as failure:
            db.commit()
        assert failure.value.orig.args[0]["C"] == "23503"
    data = b"synthetic private content"
    key = "synthetic/" + str(uuid4())
    store.client.put_object(Bucket=store.bucket, Key=key, Body=data)
    from uuid import UUID

    record = Artifact(
        workspace_id=world["workspaces"][0],
        job_id=UUID(a["id"]),
        object_key=key,
        sha256=hashlib.sha256(data).hexdigest(),
        revision=1,
        kind="synthetic",
        bytes=len(data),
    )
    try:
        with Session(world["engine"]) as db, db.begin():
            db.add(record)
            db.flush()
            rid = record.id
        with Session(runtime) as db:
            assert store.read(db, world["workspaces"][0], world["users"]["owner0"], rid) == data
            with pytest.raises(WebError) as e:
                store.read(db, world["workspaces"][1], world["users"]["owner1"], rid)
            assert e.value.status == 404
            with pytest.raises(WebError) as denied:
                store.read(db, world["workspaces"][0], world["users"]["admin"], rid)
            assert denied.value.status == 404
        unsigned = httpx.get(config.s3_endpoint + "/" + store.bucket + "/" + key, trust_env=False)
        assert unsigned.status_code in {401, 403}
    finally:
        store.client.delete_object(Bucket=store.bucket, Key=key)
    runtime.dispose()


def test_metadata_read_boundary_preserves_legacy_safety(world, tmp_path):
    order = local_store.create(tmp_path, alias="Synthetic job")
    local = LocalMetadata(tmp_path).describe(order.order_id)
    job = create(world)
    from uuid import UUID

    with Session(world["engine"]) as db:
        hosted = HostedMetadata(db, world["workspaces"][0], world["users"]["owner0"]).describe(
            UUID(job["id"])
        )
    assert (local.name, local.currency, local.status) == (
        hosted.name,
        hosted.currency,
        hosted.status,
    )
    for bad in ["../escape", job["id"]]:
        with pytest.raises(StmtconvError):
            LocalMetadata(tmp_path).describe(bad)


def test_repeat_migration_persistence_and_failures(world, monkeypatch):
    job = create(world)
    migrate(world["admin"])
    migrate(world["admin"])
    assert world["client"]("owner0").get("/api/v1/jobs/" + job["id"]).status_code == 200
    from fastapi.testclient import TestClient

    from stmtconv.web.app import create_app

    broken = world["config"].model_copy(
        update={"database_url": SecretStr("postgresql+pg8000://absent:synthetic@127.0.0.1:1/none")}
    )
    with TestClient(create_app(broken), base_url=broken.base_url) as c:
        c.cookies.set("dockling_session", "nonempty")
        response = c.get("/api/v1/session")
        assert response.status_code == 503 and "synthetic" not in response.text
    assert world["client"]("owner0").get("/api/v1/providers").status_code == 404


def test_production_config_rejects_insecure_service_and_missing_keys(world):
    values = world["config"].model_dump()
    values["mode"] = "production"
    with pytest.raises(ValidationError):
        type(world["config"])(**values)
    values["mode"] = "local"
    values["session_key"] = "short"
    with pytest.raises(ValidationError):
        type(world["config"])(**values)

    for field in ["oidc_client_secret", "s3_access_key", "s3_secret_key"]:
        values = world["config"].model_dump()
        values[field] = SecretStr("")
        with pytest.raises(ValidationError):
            type(world["config"])(**values)


def test_concurrent_final_owner_protection(world):
    c = world["client"]("owner0")
    members = c.get("/api/v1/members").json()["items"]
    editor = next(m for m in members if m["role"] == "editor")
    assert (
        c.patch(
            "/api/v1/members/" + editor["id"],
            json={"expected_version": editor["version"], "role": "owner"},
        ).status_code
        == 200
    )
    members = c.get("/api/v1/members").json()["items"]
    owners = [m for m in members if m["role"] == "owner"]

    def demote(m):
        client = world["client"]("owner0")
        return client.patch(
            "/api/v1/members/" + m["id"], json={"expected_version": m["version"], "role": "editor"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(demote, owners))
    assert sum(r.status_code == 200 for r in results) == 1
    assert all(r.status_code in {200, 403, 409} for r in results)
    with Session(world["engine"]) as db:
        remaining = list(
            db.scalars(
                select(Membership).where(
                    Membership.workspace_id == world["workspaces"][0],
                    Membership.active.is_(True),
                    Membership.role == "owner",
                )
            )
        )
    assert len(remaining) == 1


def test_worker_role_has_no_unscoped_customer_read(world):
    import json
    from pathlib import Path

    keys = json.loads(Path(".local-saas/bootstrap.json").read_text())["keys"]
    config = world["config"].model_copy(
        update={
            "database_url": SecretStr(
                "postgresql+pg8000://dockling_worker:"
                + keys["worker"]
                + "@127.0.0.1:55432/dockling_test"
            )
        }
    )
    engine = database(config)
    with engine.connect() as conn:
        with pytest.raises(ProgrammingError):
            conn.execute(text("SELECT * FROM web_jobs"))
    engine.dispose()


def test_search_and_filter_bound_cursors_are_scoped(world):
    create(world, body={**BODY, "name": "Matching A"})
    create(world, body={**BODY, "name": "Matching A second"})
    create(world, "owner1", body={**BODY, "name": "Matching A private B"})
    c = world["client"]("owner0")
    page = c.get("/api/v1/jobs", params={"search": "Matching A", "limit": 1}).json()
    assert page["next_cursor"]
    assert (
        c.get(
            "/api/v1/jobs", params={"search": "another", "cursor": page["next_cursor"]}
        ).status_code
        == 400
    )
    assert len(c.get("/api/v1/jobs", params={"search": "Matching A"}).json()["items"]) == 2
    assert c.get("/api/v1/jobs", params={"search": "private B"}).json()["items"] == []
    assert c.get("/api/v1/jobs", params={"search": "%"}).json()["items"] == []
    assert c.get("/api/v1/jobs", params={"search": "x" * 101}).status_code == 422


def test_concurrent_first_signin_maps_one_identity(world):
    from stmtconv.web.auth import create_session

    subject = str(uuid4())

    def sign_in(_):
        with Session(world["engine"]) as db, db.begin():
            return create_session(
                world["config"],
                db,
                {
                    "iss": world["config"].oidc_issuer,
                    "sub": subject,
                    "email": "new@example.test",
                    "email_verified": True,
                },
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(sign_in, range(4)))
    assert len(set(tokens)) == 4
    with Session(world["engine"]) as db:
        users = list(db.scalars(select(User).where(User.subject == subject)))
        assert len(users) == 1
        sessions = list(db.scalars(select(WebSession).where(WebSession.user_id == users[0].id)))
        assert len(sessions) == 4 and all(s.workspace_id is None and not s.mfa for s in sessions)
