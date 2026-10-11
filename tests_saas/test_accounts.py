"""Real PostgreSQL/storage account, manual payment evidence and quota boundaries."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from test_foundation import create
from test_pipeline import upload
from test_review import converted
from test_review import worker as worker

from stmtconv.web.database import database
from stmtconv.web.models import (
    AccountCommand,
    BillingEvidence,
    Entitlement,
    PageReservation,
    User,
    now,
)

PLAN = {
    "name": "Fictional pilot",
    "pages_per_month": 100,
    "seats": 4,
    "monthly_amount": "25.00",
    "currency": "USD",
    "approved_for_customers": False,
}


def post(client, path, body):
    client.headers["Idempotency-Key"] = str(uuid4())
    return client.post(path, json=body)


def invoice(world):
    admin = world["client"]("admin")
    plan = post(admin, "/api/v1/admin/plans", PLAN)
    assert plan.status_code == 201, plan.text
    ws = str(world["workspaces"][0])
    created = post(
        admin, f"/api/v1/admin/workspaces/{ws}/invoices", {"plan_id": plan.json()["id"], "days": 30}
    )
    assert created.status_code == 201, created.text
    path = f"/api/v1/admin/workspaces/{ws}/invoices/{created.json()['id']}/evidence"
    return admin, path, created.json()


def event(admin, path, record, status, **extra):
    result = post(
        admin,
        path,
        {
            "expected_version": record["version"],
            "status": status,
            "reference": uuid4().hex,
            "verified_evidence": True,
            **extra,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_manual_invoice_exact_immutable_mfa_idempotency_and_owner_scope(world):
    admin, path, record = invoice(world)
    ws = str(world["workspaces"][0])
    for who in ("owner0", "editor0", "viewer0", "admin-no-mfa", "outsider"):
        assert post(world["client"](who), "/api/v1/admin/plans", PLAN).status_code == 403
        assert world["client"](who).get(f"/api/v1/admin/workspaces/{ws}/billing").status_code == 403
    for value in (25.0, "NaN", "25.0", "-25.00", "0.00"):
        assert (
            post(admin, "/api/v1/admin/plans", {**PLAN, "monthly_amount": value}).status_code == 422
        )
    assert (
        post(admin, "/api/v1/admin/plans", {**PLAN, "approved_for_customers": True}).status_code
        == 409
    )
    owner = world["client"]("owner0")
    assert owner.get("/api/v1/plans").json()["items"] == []
    assert owner.get("/api/v1/billing").json()["invoices"][0]["amount"] == "25.00"
    assert world["client"]("owner1").get("/api/v1/billing").json()["invoices"] == []
    for who in ("editor0", "viewer0", "admin"):
        assert world["client"](who).get("/api/v1/billing").status_code in (403, 404)
    assert post(owner, "/api/v1/billing/checkout", {}).status_code == 409
    assert post(world["client"]("viewer0"), "/api/v1/billing/checkout", {}).status_code == 403
    assert (
        post(
            owner,
            path,
            {
                "expected_version": 1,
                "status": "paid",
                "reference": uuid4().hex,
                "verified_evidence": True,
            },
        ).status_code
        == 403
    )
    assert (
        post(
            admin,
            path,
            {
                "expected_version": 1,
                "status": "paid",
                "reference": uuid4().hex,
                "verified_evidence": True,
            },
        ).status_code
        == 409
    )
    command = {
        "expected_version": 1,
        "status": "issued",
        "reference": uuid4().hex,
        "verified_evidence": True,
    }
    result = post(admin, path, command)
    assert result.status_code == 200
    assert admin.post(path, json=command).json() == result.json()
    assert post(admin, path, command).status_code == 409
    assert (
        post(
            admin,
            path,
            {**command, "expected_version": 2, "status": "failed", "verified_evidence": False},
        ).status_code
        == 409
    )
    record = event(admin, path, result.json(), "failed")
    assert owner.get("/api/v1/usage").json()["status"] == "development"
    record = event(admin, path, record, "issued")
    record = event(admin, path, record, "paid")
    assert owner.get("/api/v1/usage").json()["page_limit"] == 100
    with Session(world["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(BillingEvidence)) == 4
    app_engine = database(world["config"])
    try:
        with pytest.raises(ProgrammingError) as error, app_engine.begin() as connection:
            connection.execute(text("UPDATE web_commercial_plans SET data='{}'::jsonb"))
        assert error.value.orig.args[0]["C"] == "42501"
    finally:
        app_engine.dispose()


@pytest.mark.parametrize("outcome", ["refunded", "cancelled"])
def test_revocation_fences_actual_worker_and_keeps_existing_data(world, worker, tmp_path, outcome):
    c, jid = converted(world, worker, tmp_path)
    admin, path, record = invoice(world)
    record = event(admin, path, record, "issued")
    record = event(admin, path, record, "paid")
    used = c.get("/api/v1/usage").json()["pages_used"]
    queued = post(
        c, f"/api/v1/jobs/{jid}/operations", {"expected_revision": 4, "action": "extract"}
    )
    assert queued.status_code == 202, queued.text
    token = uuid4().hex + uuid4().hex
    task = worker.claim(token)
    assert task
    record = event(admin, path, record, outcome)
    assert c.get("/api/v1/usage").json()["processing_allowed"] is False
    assert c.get("/api/v1/usage").json()["pages_used"] == used
    assert not worker.publish(
        task, token, {"state": "succeeded", "digest": "a" * 64, "statements": []}
    )
    assert c.get(f"/api/v1/jobs/{jid}/rows").status_code == 200
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 4
    assert (
        post(
            c, f"/api/v1/jobs/{jid}/operations", {"expected_revision": 4, "action": "extract"}
        ).status_code
        == 403
    )
    assert (
        post(
            c,
            f"/api/v1/jobs/{jid}/ai/requests",
            {"expected_revision": 4, "consent_version": 1, "page_keys": ["a" * 64]},
        ).status_code
        == 403
    )
    assert (
        post(
            admin,
            path,
            {
                "expected_version": record["version"],
                "status": "paid",
                "reference": uuid4().hex,
                "verified_evidence": True,
            },
        ).status_code
        == 409
    )


def test_expiry_retains_ledger_and_has_no_development_fallback(world):
    admin, path, record = invoice(world)
    record = event(admin, path, record, "issued")
    event(admin, path, record, "paid")
    with Session(world["engine"]) as db, db.begin():
        item = db.get(Entitlement, world["workspaces"][0])
        assert item
        item.valid_until = now() - timedelta(seconds=1)
    response = world["client"]("owner0").get("/api/v1/usage").json()
    assert (
        response["status"] == "expired"
        and response["page_limit"] == 0
        and not response["processing_allowed"]
    )


def test_concurrent_page_reservations_atomic_replay_and_failed_inspection(world, monkeypatch):
    monkeypatch.setattr(world["config"], "development_page_allowance", 40)
    jobs = [create(world)["id"] for _ in range(2)]
    clients = [world["client"]("owner0") for _ in jobs]
    for c, jid in zip(clients, jobs, strict=True):
        assert upload(c, jid).status_code == 200
        c.headers["Idempotency-Key"] = uuid4().hex
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(
                lambda item: item[0].post(
                    f"/api/v1/jobs/{item[1]}/intake", json={"expected_revision": 2}
                ),
                zip(clients, jobs, strict=True),
            )
        )
    assert sorted(r.status_code for r in responses) == [202, 429]
    accepted = next(i for i, r in enumerate(responses) if r.status_code == 202)
    repeat = clients[accepted].post(
        f"/api/v1/jobs/{jobs[accepted]}/intake", json={"expected_revision": 2}
    )
    assert repeat.json() == responses[accepted].json()
    usage = clients[0].get("/api/v1/usage").json()
    assert (
        usage["pages_reserved"] == 40 and usage["pages_used"] == 0 and usage["pages_remaining"] == 0
    )
    with Session(world["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(PageReservation)) == 1


def test_settlement_reuses_source_budget(world, worker, tmp_path):
    c, jid = converted(world, worker, tmp_path)
    usage = c.get("/api/v1/usage").json()
    assert usage["pages_reserved"] == 0 and usage["pages_used"] == 1
    assert (
        post(
            c, f"/api/v1/jobs/{jid}/operations", {"expected_revision": 4, "action": "extract"}
        ).status_code
        == 202
    )
    assert c.get("/api/v1/usage").json()["pages_used"] == 1


def test_pending_seats_email_binding_revocation_and_concurrency(world, monkeypatch):
    monkeypatch.setattr(world["config"], "development_seats", 4)
    clients = [world["client"]("owner0") for _ in range(2)]
    emails = ["outsider@example.test", "owner1@example.test"]
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda item: post(
                    item[0], "/api/v1/invitations", {"email": item[1], "role": "viewer"}
                ),
                zip(clients, emails, strict=True),
            )
        )
    assert sorted(r.status_code for r in results) == [201, 409]
    accepted = next(i for i, r in enumerate(results) if r.status_code == 201)
    inv = results[accepted].json()
    token = inv["accept_url"].split("#")[1]
    right = "outsider" if accepted == 0 else "owner1"
    wrong = "owner1" if accepted == 0 else "outsider"
    assert (
        post(world["client"](wrong), "/api/v1/invitations/accept", {"token": token}).status_code
        == 404
    )
    listing = clients[0].get("/api/v1/invitations").json()["items"]
    assert len(listing) == 1 and "token" not in str(listing) and token not in str(listing)
    assert world["client"]("viewer0").get("/api/v1/invitations").status_code == 403
    assert (
        post(world["client"](right), "/api/v1/invitations/accept", {"token": token}).status_code
        == 200
    )
    assert clients[0].get("/api/v1/usage").json()["active_seats"] == 4
    assert clients[0].get("/api/v1/usage").json()["pending_invitations"] == 0


def test_verified_onboarding_no_membership_account_replay_and_cap(world):
    c = world["client"]("outsider")
    result = post(c, "/api/v1/workspaces", {"name": "Fictional newly invited team"})
    assert result.status_code == 201, result.text
    assert (
        c.post("/api/v1/workspaces", json={"name": "Fictional newly invited team"}).json()
        == result.json()
    )
    assert c.post("/api/v1/workspaces", json={"name": "Different name"}).status_code == 409
    assert c.get("/api/v1/session").json()["role"] == "owner"
    assert c.get("/api/v1/jobs").json()["items"] == []
    with Session(world["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(AccountCommand)) == 1
    for name in ("Second", "Third"):
        assert post(c, "/api/v1/workspaces", {"name": name}).status_code == 201
    assert post(c, "/api/v1/workspaces", {"name": "Fourth"}).status_code == 429
    with Session(world["engine"]) as db, db.begin():
        user = db.get(User, world["users"]["owner1"])
        assert user
        user.email_verified = False
    assert (
        post(world["client"]("owner1"), "/api/v1/workspaces", {"name": "Unverified"}).status_code
        == 403
    )


def test_private_requests_notices_mfa_scope_and_no_implicit_document_access(world):
    owner = world["client"]("owner0")
    viewer = world["client"]("viewer0")
    created = post(
        viewer, "/api/v1/requests", {"kind": "support", "message": "Fictional help request"}
    )
    assert created.status_code == 201, created.text
    assert (
        post(
            viewer, "/api/v1/requests", {"kind": "privacy_remove", "message": "Remove team"}
        ).status_code
        == 403
    )
    assert (
        post(
            owner,
            "/api/v1/requests",
            {"kind": "privacy_remove", "message": "Please explain workspace removal"},
        ).status_code
        == 201
    )
    assert len(owner.get("/api/v1/requests").json()["items"]) == 2
    assert len(viewer.get("/api/v1/requests").json()["items"]) == 1
    assert world["client"]("owner1").get("/api/v1/requests").json()["items"] == []
    assert world["client"]("admin-no-mfa").get("/api/v1/admin/requests").status_code == 403
    admin = world["client"]("admin")
    response = post(
        admin,
        "/api/v1/admin/requests/" + created.json()["id"] + "/response",
        {
            "expected_version": 1,
            "status": "answered",
            "response": "Fictional answer without customer documents",
        },
    )
    assert response.status_code == 200, response.text
    assert (
        viewer.get("/api/v1/requests").json()["items"][0]["response"] == response.json()["response"]
    )
    notices = viewer.get("/api/v1/notices").json()["items"]
    assert notices and "Fictional help request" not in str(notices)
    nid = notices[0]["id"]
    assert post(viewer, "/api/v1/notices/" + nid + "/read", {}).status_code == 200
    assert (
        post(world["client"]("owner1"), "/api/v1/notices/" + nid + "/read", {}).status_code == 404
    )
    assert post(viewer, "/api/v1/notices/" + nid + "/read", {}).status_code == 200
    create(world)
    assert admin.get("/api/v1/jobs").status_code == 404
    viewer.headers.pop("X-CSRF-Token")
    assert (
        post(viewer, "/api/v1/requests", {"kind": "support", "message": "CSRF denied"}).status_code
        == 403
    )
