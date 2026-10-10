"""Hosted consent/budgets/uncertainty/privacy with real PG and fake provider calls."""

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_review import converted, workflow_run
from test_review import worker as worker

from stmtconv.web import connections
from stmtconv.web.models import AiAttempt, AiConsent, AiRun, CanonicalSnapshot, Job, Membership


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    from stmtconv.web.egress import PinnedHTTPS

    def blocked(_self):
        raise AssertionError("Unexpected live provider call")

    monkeypatch.setattr(PinnedHTTPS, "connect", blocked)


def post(c, path, rev, **fields):
    c.headers["Idempotency-Key"] = str(uuid4())
    return c.post(path, json={"expected_revision": rev, **fields})


def connection(c):
    c.headers["Idempotency-Key"] = str(uuid4())
    r = c.post(
        "/api/v1/connections",
        json={
            "name": "Fictional generation",
            "base_url": "https://api.example.com/v1",
            "requires_key": False,
        },
    )
    assert r.status_code == 201, r.text
    identifier = r.json()["id"]
    path = "/api/v1/connections/" + identifier
    assert post(c, path + "/models/manual", 1, model_id="fictional").status_code == 200
    assert (
        post(c, path + "/selection", 2, model_id="fictional", effort="highest").status_code == 200
    )
    assert (
        post(
            c, path + "/terms", 3, confirmed=True, terms_version="https://example.com/terms/v1"
        ).status_code
        == 200
    )
    return identifier


def grant(c, jid, rev, conn, version=0, cap=5, names=None):
    r = post(
        c,
        f"/api/v1/jobs/{jid}/consent",
        rev,
        expected_consent_version=version,
        granted=True,
        connection_id=conn,
        consent_note="Fictional client explicitly permitted minimized cells",
        mask_names=names or [],
        page_cap=cap,
        request_cap=cap,
    )
    assert r.status_code == 200, r.text
    return r.json()


class Fake:
    calls = []
    callback = None

    def __init__(self, provider):
        self.provider = provider

    def request(self, method, route, body=None):
        assert method == "POST" and route == "/chat/completions"
        self.calls.append(body)
        if self.callback:
            self.callback()
        content = body["messages"][1]["content"].split("Only transaction cells follow:\n", 1)[1]
        return {"choices": [{"message": {"content": json.dumps(json.loads(content))}}]}


@pytest.fixture
def fake(monkeypatch):
    Fake.calls = []
    Fake.callback = None
    monkeypatch.setattr(connections, "transport", Fake)
    return Fake


def request(c, jid, status, ack=False):
    return post(
        c,
        f"/api/v1/jobs/{jid}/ai/requests",
        status["revision"],
        consent_version=status["consent"]["version"],
        page_keys=[status["pages"][0]["key"]],
        acknowledge_prior_uncertainty=ack,
    )


def test_consent_gate_binding_budget_model_change_and_no_cap_reset(world, worker, tmp_path, fake):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = c.get(f"/api/v1/jobs/{jid}/ai").json()
    assert status["consent"] is None and status["pages_used"] == 0
    assert (
        post(
            c,
            f"/api/v1/jobs/{jid}/ai/requests",
            4,
            consent_version=1,
            page_keys=[status["pages"][0]["key"]],
        ).status_code
        == 409
    )
    status = grant(c, jid, 4, conn, cap=1)
    r = request(c, jid, status)
    assert r.status_code == 202, r.text
    assert (
        c.post(
            f"/api/v1/jobs/{jid}/ai/requests",
            json={
                "expected_revision": 4,
                "consent_version": 1,
                "page_keys": [status["pages"][0]["key"]],
                "acknowledge_prior_uncertainty": False,
            },
        ).json()
        == r.json()
    )
    assert world["app"].state.ai_gateway.process_one()
    assert len(fake.calls) == 1
    after = c.get(f"/api/v1/jobs/{jid}/ai").json()
    assert after["revision"] == 5 and after["pages_used"] == 1 and not after["consent"]["valid"]
    status = grant(c, jid, 5, conn, version=1, cap=1)
    assert request(c, jid, status).status_code == 429
    assert status["pages_used"] == 1
    row = c.get(f"/api/v1/jobs/{jid}/rows").json()["items"][0]
    assert row["engine"] == "ai" and row["fixed_by"] == "ai" and not row["source_reviewed"]
    assert c.get(f"/api/v1/jobs/{jid}").json()["source_checked"] is False
    assert post(c, f"/api/v1/jobs/{jid}/exports", 5).status_code == 409


def test_uncertain_send_no_automatic_retry_and_informed_new_reservation(
    world, worker, tmp_path, fake
):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = grant(c, jid, 4, conn, cap=3)

    def timeout():
        raise TimeoutError("potentially billed provider request")

    fake.callback = staticmethod(timeout)
    assert request(c, jid, status).status_code == 202
    assert world["app"].state.ai_gateway.process_one()
    assert len(fake.calls) == 1 and not world["app"].state.ai_gateway.process_one()
    after = c.get(f"/api/v1/jobs/{jid}/ai").json()
    assert after["runs"][0]["state"] == "uncertain" and after["pages_used"] == 1
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 4
    assert request(c, jid, after).status_code == 409
    r = request(c, jid, after, ack=True)
    assert r.status_code == 202 and r.json()["id"] != after["runs"][0]["id"]
    assert c.get(f"/api/v1/jobs/{jid}/ai").json()["pages_used"] == 2
    fake.callback = None
    assert world["app"].state.ai_gateway.process_one()
    assert len(fake.calls) == 2


def test_scope_roles_consent_revocation_and_configuration_fence(world, worker, tmp_path, fake):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    for name in ("editor0", "viewer0", "owner1", "admin"):
        other = world["client"](name)
        r = post(
            other,
            f"/api/v1/jobs/{jid}/consent",
            4,
            expected_consent_version=0,
            granted=True,
            connection_id=conn,
            consent_note="fictional",
        )
        assert r.status_code == (403 if name in ("editor0", "viewer0") else 404)
    status = grant(c, jid, 4, conn)
    for name in ("viewer0", "owner1", "admin"):
        assert request(world["client"](name), jid, status).status_code == (
            403 if name == "viewer0" else 404
        )
    assert request(c, jid, status).status_code == 202
    post(
        c,
        "/api/v1/connections/" + conn + "/selection",
        4,
        model_id="fictional",
        effort="provider_default",
    )
    assert world["app"].state.ai_gateway.process_one()
    assert fake.calls == []
    assert c.get(f"/api/v1/jobs/{jid}/ai").json()["pages_used"] == 1
    status = grant(c, jid, 4, conn, version=1)
    assert request(c, jid, status).status_code == 202
    assert (
        post(
            c, f"/api/v1/jobs/{jid}/consent", 4, expected_consent_version=2, granted=False
        ).status_code
        == 200
    )
    assert not world["app"].state.ai_gateway.process_one()
    assert fake.calls == []


def test_cancel_during_send_blocks_publication_and_removal_waits_for_memory(
    world, worker, tmp_path, fake
):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = grant(c, jid, 4, conn)
    result = request(c, jid, status)

    def abandon():
        r = post(c, f"/api/v1/jobs/{jid}/close", 4, confirm_removal=True, abandon_unfinished=True)
        assert r.status_code == 202
        token = uuid4().hex + uuid4().hex
        assert (
            worker.claim(token) is None
        )  # Close cannot certify while the gateway holds private cells.

    fake.callback = staticmethod(abandon)
    assert world["app"].state.ai_gateway.process_one()
    assert len(fake.calls) == 1
    with Session(world["engine"]) as db:
        run = db.get(AiRun, UUID(result.json()["id"]))
        assert run.state == "cancelled" and run.cleanup_done
        assert db.get(Job, UUID(jid)).revision == 5
    workflow_run(world, worker, tmp_path)
    assert c.get(f"/api/v1/jobs/{jid}/privacy").json()["certificate"]
    with Session(world["engine"]) as db:
        for model in (AiRun, AiAttempt, AiConsent, CanonicalSnapshot):
            assert db.scalar(select(model.job_id).where(model.job_id == UUID(jid))) is None


def test_masked_payload_no_identifiers_source_headers_or_keys(world, worker, tmp_path, fake):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    with Session(world["engine"]) as db, db.begin():
        record = db.scalar(
            select(CanonicalSnapshot).where(
                CanonicalSnapshot.job_id == UUID(jid), CanonicalSnapshot.revision == 4
            )
        )
        data = json.loads(json.dumps(record.statements))
        data[0]["domain"]["transactions"][0]["description"] = (
            "Alice Smith alice@example.test +1 202 555 0181 account 123456789012"
        )
        data[0]["domain"]["transactions"][0]["raw_text"] = "NEVER SEND raw header with SECRET"
        record.statements = data
    status = grant(c, jid, 4, conn, names=["Alice Smith"])
    assert request(c, jid, status).status_code == 202
    assert world["app"].state.ai_gateway.process_one()
    sent = json.dumps(fake.calls)
    assert len(fake.calls) == 1
    for private in (
        "Alice Smith",
        "alice@example.test",
        "123456789012",
        "202 555 0181",
        "NEVER SEND",
        "SECRET",
        jid,
        conn,
    ):
        assert private not in sent
    assert "[NAME REDACTED]" in sent


def test_atomic_multi_page_response_and_invalid_money_never_partially_apply(
    world, worker, tmp_path, fake, monkeypatch
):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    with Session(world["engine"]) as db, db.begin():
        record = db.scalar(
            select(CanonicalSnapshot).where(
                CanonicalSnapshot.job_id == UUID(jid), CanonicalSnapshot.revision == 4
            )
        )
        original = json.loads(json.dumps(record.statements))
        original[0]["domain"]["transactions"][1]["page"] = 2
        original[0]["domain"]["pages"] = [1, 2]
        record.statements = original
    status = grant(c, jid, 4, conn)
    count = []

    def invalid(self, method, route, body):
        count.append(body)
        content = body["messages"][1]["content"].split("Only transaction cells follow:\n", 1)[1]
        value = json.loads(content)
        if len(count) == 2:
            value["rows"][0]["debit"] = "NaN"
        return {"choices": [{"message": {"content": json.dumps(value)}}]}

    monkeypatch.setattr(Fake, "request", invalid)
    response = post(
        c,
        f"/api/v1/jobs/{jid}/ai/requests",
        4,
        consent_version=1,
        page_keys=[p["key"] for p in status["pages"]],
    )
    assert response.status_code == 202
    assert world["app"].state.ai_gateway.process_one()
    assert len(count) == 2
    after = c.get(f"/api/v1/jobs/{jid}/ai").json()
    assert after["runs"][0]["state"] == "failed" and after["pages_used"] == 2
    assert after["revision"] == 4
    with Session(world["engine"]) as db:
        record = db.scalar(
            select(CanonicalSnapshot).where(
                CanonicalSnapshot.job_id == UUID(jid), CanonicalSnapshot.revision == 4
            )
        )
        assert record.statements == original


def test_consent_csrf_stale_pages_and_queued_edit_denial(world, worker, tmp_path, fake):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = grant(c, jid, 4, conn)
    assert (
        post(
            c,
            f"/api/v1/jobs/{jid}/ai/requests",
            3,
            consent_version=1,
            page_keys=[status["pages"][0]["key"]],
        ).status_code
        == 409
    )
    assert (
        post(
            c, f"/api/v1/jobs/{jid}/ai/requests", 4, consent_version=1, page_keys=["0" * 64]
        ).status_code
        == 422
    )
    c.headers["X-CSRF-Token"] = "forged"
    assert request(c, jid, status).status_code == 403
    c = world["client"]("owner0")
    assert request(c, jid, status).status_code == 202
    row = c.get(f"/api/v1/jobs/{jid}/rows").json()["items"][0]
    r = c.patch(
        f"/api/v1/jobs/{jid}/review",
        json={
            "expected_revision": 4,
            "edits": [
                {
                    "statement_id": row["statement_id"],
                    "row_id": row["id"],
                    "action": "fix",
                    "changes": {"description": "Should stay unchanged"},
                }
            ],
        },
    )
    assert r.status_code == 409
    assert fake.calls == []


def test_consent_owner_removal_fences_editor_dispatch(world, worker, tmp_path, fake):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = grant(c, jid, 4, conn)
    assert request(world["client"]("editor0"), jid, status).status_code == 202
    with Session(world["engine"]) as db, db.begin():
        owner = db.scalar(select(Membership).where(Membership.user_id == world["users"]["owner0"]))
        owner.active = False
    assert world["app"].state.ai_gateway.process_one()
    assert fake.calls == []
    assert world["client"]("editor0").get(f"/api/v1/jobs/{jid}/ai").json()["pages_used"] == 1


def test_crash_send_recovery_retains_uncertainty_and_hosted_cleanup_fence(
    world, worker, tmp_path, fake
):
    c, jid = converted(world, worker, tmp_path)
    conn = connection(c)
    status = grant(c, jid, 4, conn)
    queued = request(c, jid, status).json()
    with Session(world["engine"]) as db, db.begin():
        run = db.get(AiRun, UUID(queued["id"]))
        run.state, run.cleanup_done = "running", False
        attempt = db.scalar(select(AiAttempt).where(AiAttempt.run_id == run.id))
        attempt.state = "sending"
    gateway = world["app"].state.ai_gateway
    gateway._recover(False)
    safe = c.get(f"/api/v1/jobs/{jid}/ai").json()
    assert safe["runs"][0]["state"] == "uncertain" and not safe["runs"][0]["cleanup_done"]
    assert safe["pages_used"] == 1 and fake.calls == []
    assert request(c, jid, status).status_code == 409
    # Local restart may acknowledge only after the serving path holds its OS + DB locks.
    gateway._recover(True)
    assert c.get(f"/api/v1/jobs/{jid}/ai").json()["runs"][0]["cleanup_done"]
    assert request(c, jid, status).status_code == 409  # still requires informed uncertainty retry
