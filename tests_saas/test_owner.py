"""Owner/admin boundaries against real PostgreSQL, scoped worker and private storage."""

import base64
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_foundation import create
from test_review import converted, post, workflow_run
from test_review import worker as worker

from stmtconv.config import load_settings
from stmtconv.web.models import (
    Artifact,
    ConfigVersion,
    Event,
    Job,
    Membership,
    ServiceReport,
    SupportGrant,
    now,
)
from stmtconv.web.owner_config import baseline
from stmtconv.web.pipeline import compute


def put(c, path, data):
    c.headers["Idempotency-Key"] = str(uuid4())
    return c.put(path, json=data)


def test_preferences_owner_version_exact_scope_and_existing_jobs(world):
    c = world["client"]("owner0")
    jid = create(world)["id"]
    old = c.get("/api/v1/jobs/" + jid).json()["options"]
    command = {
        "expected_version": 0,
        "currency": "EUR",
        "date_order": "DMY",
        "output_date_format": "DD/MM/YYYY",
        "outputs": ["csv", "ofx"],
    }
    for who in ("editor0", "viewer0", "admin"):
        assert world["client"](who).put("/api/v1/settings", json=command).status_code in (403, 404)
    result = put(c, "/api/v1/settings", command)
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 1
    assert c.put("/api/v1/settings", json=command).json() == result.json()
    assert put(c, "/api/v1/settings", command).status_code == 409
    assert world["client"]("owner1").get("/api/v1/settings").json()["currency"] == "USD"
    assert c.get("/api/v1/jobs/" + jid).json()["options"] == old
    assert (
        put(
            c, "/api/v1/settings", {**command, "expected_version": 1, "outputs": ["csv", "csv"]}
        ).status_code
        == 422
    )
    c.headers.pop("X-CSRF-Token")
    assert put(c, "/api/v1/settings", {**command, "expected_version": 1}).status_code == 403


def test_config_immutable_draft_activation_snapshots_and_mfa(world):
    admin = world["client"]("admin")
    owner = world["client"]("owner0")
    jid = create(world)["id"]
    path = "/api/v1/admin/config/processing"
    command = {
        "expected_version": 0,
        "data": {**baseline("processing"), "qb_csv_max_rows": 10},
        "reason": "Synthetic configuration review",
    }
    for who in ("owner0", "editor0", "admin-no-mfa"):
        assert world["client"](who).get(path).status_code == 403
        assert world["client"](who).put(path, json=command).status_code == 403
    draft = put(admin, path, command)
    assert draft.status_code == 200, draft.text
    assert draft.json()["active_version"] is None
    assert draft.json()["active_data"]["qb_csv_max_rows"] == 1000
    active = put(admin, path, {**command, "expected_version": 1, "activate": True})
    assert active.status_code == 200, active.text
    assert active.json()["active_version"] == 2 and len(active.json()["history"]) == 2
    new_id = create(world)["id"]
    with Session(world["engine"]) as db:
        assert db.get(Job, UUID(jid)).runtime_config["processing"]["qb_csv_max_rows"] == 1000
        assert db.get(Job, UUID(new_id)).runtime_config["processing"]["qb_csv_max_rows"] == 10
        assert (
            db.scalar(select(ConfigVersion).where(ConfigVersion.version == 1)).data[
                "qb_csv_max_rows"
            ]
            == 10
        )
    for data in (
        {**baseline("processing"), "balance_tolerance": "0.10"},
        {**baseline("processing"), "balance_tolerance": 0.001},
        {**baseline("processing"), "unknown": True},
    ):
        assert put(admin, path, {**command, "expected_version": 2, "data": data}).status_code == 422
    exports = baseline("exports")
    exports["formats"]["csv"]["columns"] = ["broken"]
    assert (
        put(admin, "/api/v1/admin/config/exports", {**command, "data": exports}).status_code == 422
    )
    pricing = baseline("pricing")
    pricing["addons"]["synthetic"] = 0.1
    assert (
        put(admin, "/api/v1/admin/config/pricing", {**command, "data": pricing}).status_code == 422
    )
    assert admin.get("/api/v1/jobs/" + jid).status_code == 404
    assert owner.get("/api/v1/admin/diagnostics/" + new_id).status_code == 403


def test_private_scaffold_scoped_worker_download_and_close(world, worker, tmp_path):
    c, jid = converted(world, worker, tmp_path)
    file = c.get("/api/v1/jobs/" + jid + "/files").json()["items"][0]
    path = "/api/v1/jobs/" + jid + "/profile-scaffolds"
    for who in ("editor0", "viewer0", "owner1", "admin"):
        assert post(world["client"](who), path, 4, file_id=file["id"]).status_code in (403, 404)
    assert post(c, path, 4, file_id=str(uuid4())).status_code == 404
    queued = post(c, path, 4, file_id=file["id"])
    assert queued.status_code == 202, queued.text
    token = uuid4().hex * 2
    task = worker.claim(token)
    assert task.action == "profile_scaffold"

    def call(action, **values):
        return world["app"].state.broker.call(
            {
                "operation": str(task.id),
                "generation": task.generation,
                "token": token,
                "action": action,
                **values,
            }
        )

    call("scratch_begin")
    raw = base64.b64decode(call("read", artifact=task.payload["source_artifact"])["data"])
    result = compute(task, {"source": raw}, {}, tmp_path, load_settings(), 40)
    for a in result.artifacts:
        call("stage", artifact=str(a.id), kind=a.kind, data=base64.b64encode(a.data).decode())
    assert worker.publish(task, token, result.record)
    call("scratch_end")
    assert c.get("/api/v1/jobs/" + jid).json()["revision"] == 4
    items = c.get("/api/v1/jobs/" + jid + "/utilities").json()["items"]
    assert len(items) == 1
    download = "/api/v1/jobs/" + jid + "/utilities/" + items[0]["id"] + "/download"
    assert c.get(download).json()["page_1_words"]
    for who in ("editor0", "viewer0", "admin", "owner1"):
        assert world["client"](who).get(download).status_code in (403, 404)
    assert (
        post(
            c, "/api/v1/jobs/" + jid + "/close", 4, confirm_removal=True, abandon_unfinished=True
        ).status_code
        == 202
    )
    workflow_run(world, worker, tmp_path)
    assert c.get(download).status_code == 404
    with Session(world["engine"]) as db:
        assert db.get(Job, UUID(jid)).runtime_config == {}
        assert list(db.scalars(select(Artifact).where(Artifact.job_id == UUID(jid)))) == []


def test_synthetic_profile_evidence_and_real_selftest(world, worker, tmp_path):
    admin = world["client"]("admin")
    profile = baseline("profile_generic")
    path = "/api/v1/admin/config/profile_generic"
    command = {
        "expected_version": 0,
        "data": profile,
        "reason": "Synthetic profile approval",
        "activate": True,
        "synthetic_review_confirmed": True,
    }
    assert put(admin, path, command).status_code == 409
    q = post(admin, "/api/v1/admin/profiles/generic/tests", 1, profile=profile)
    # ProfileTest has no revision field: strict command rejects it.
    assert q.status_code == 422
    admin.headers["Idempotency-Key"] = str(uuid4())
    q = admin.post("/api/v1/admin/profiles/generic/tests", json={"profile": profile})
    assert q.status_code == 202, q.text
    workflow_run(world, worker, tmp_path, scratch=True)
    report = admin.get("/api/v1/admin/diagnostics/" + q.json()["job_id"]).json()
    assert report["evidence"][0]["passed"] is True, report
    aid = report["evidence"][0]["artifact_id"]
    raw = admin.get("/api/v1/admin/diagnostics/" + q.json()["job_id"] + "/" + aid + "/download")
    assert raw.status_code == 200 and raw.json()["matched"] is True
    assert put(admin, path, {**command, "evidence_id": aid}).status_code == 200
    changed = {**profile, "display_name": "A different exact profile"}
    assert (
        put(
            admin, path, {**command, "expected_version": 1, "data": changed, "evidence_id": aid}
        ).status_code
        == 409
    )
    assert (
        world["client"]("owner0").get("/api/v1/admin/diagnostics/" + q.json()["job_id"]).status_code
        == 403
    )
    admin.headers["Idempotency-Key"] = str(uuid4())
    q = admin.post("/api/v1/admin/selftest", json={})
    assert q.status_code == 202, q.text
    workflow_run(world, worker, tmp_path, scratch=True)
    r = admin.get("/api/v1/admin/diagnostics/" + q.json()["job_id"]).json()
    aid = r["reports"][0]["id"]
    result = admin.get(
        "/api/v1/admin/diagnostics/" + q.json()["job_id"] + "/" + aid + "/download"
    ).json()
    assert result["passed"] is True and len(result["results"]) == 9


def test_named_support_scope_revision_revoke_expiry_owner_and_audit(world, worker, tmp_path):
    owner, jid = converted(world, worker, tmp_path)
    admin = world["client"]("admin")
    path = "/api/v1/jobs/" + jid + "/support-grants"
    command = {
        "actor_id": str(world["users"]["admin"]),
        "scopes": ["results"],
        "minutes": 10,
        "reason": "Synthetic support test",
    }
    for who in ("editor0", "viewer0", "owner1", "admin"):
        assert post(world["client"](who), path, 4, **command).status_code in (403, 404)
    assert post(owner, path, 4, **{**command, "minutes": 61}).status_code == 422
    grant = post(owner, path, 4, **command)
    assert grant.status_code == 201, grant.text
    gid = grant.json()["id"]
    delegated = "/api/v1/admin/support-grants/" + gid
    assert admin.get(delegated + "/results").status_code == 200
    assert world["client"]("admin-no-mfa").get(delegated + "/results").status_code == 403
    assert world["client"]("owner0").get(delegated + "/results").status_code == 403
    with Session(world["engine"]) as db:
        aid = db.scalar(
            select(Artifact.id).where(Artifact.job_id == UUID(jid), Artifact.kind == "normalized")
        )
        assert (
            db.scalar(
                select(Event).where(
                    Event.job_id == UUID(jid), Event.action == "support.results.read"
                )
            )
            is not None
        )
    assert admin.get(delegated + "/artifacts/" + str(aid)).status_code == 404
    assert admin.get(delegated + "/artifacts").status_code == 404
    source_grant = post(owner, path, 4, **{**command, "scopes": ["source"]}).json()
    source_path = "/api/v1/admin/support-grants/" + source_grant["id"]
    assert any(i["id"] == str(aid) for i in admin.get(source_path + "/artifacts").json()["items"])
    assert admin.get(source_path + "/artifacts/" + str(aid)).status_code == 200
    assert admin.get(source_path + "/results").status_code == 404
    assert world["client"]("admin-no-mfa").get(source_path + "/artifacts").status_code == 403
    assert admin.get("/api/v1/jobs/" + jid).status_code == 404
    assert post(owner, path + "/" + gid + "/revoke", 4, expected_version=1).status_code == 200
    assert admin.get(delegated + "/results").status_code == 404
    for cause in ("expiry", "owner", "revision"):
        grant = post(owner, path, 4, **command)
        assert grant.status_code == 201
        gid = grant.json()["id"]
        with Session(world["engine"]) as db, db.begin():
            if cause == "expiry":
                db.get(SupportGrant, UUID(gid)).expires_at = now() - timedelta(seconds=1)
            if cause == "owner":
                m = db.scalar(
                    select(Membership).where(Membership.user_id == world["users"]["owner0"])
                )
                m.active = False
            if cause == "revision":
                db.get(Job, UUID(jid)).revision += 1
        assert admin.get("/api/v1/admin/support-grants/" + gid + "/results").status_code == 404
        with Session(world["engine"]) as db, db.begin():
            if cause == "owner":
                db.scalar(
                    select(Membership).where(Membership.user_id == world["users"]["owner0"])
                ).active = True


def test_health_no_fabricated_models_and_small_group_metrics(world, worker):
    admin = world["client"]("admin")
    assert admin.get("/api/v1/admin/health").json()["models"] == "unknown"
    with worker.engine.begin() as connection:
        assert (
            connection.scalar(
                text("SELECT dockling_worker_report(:d,'test',true)"), {"d": "a" * 64}
            )
            is True
        )
    report = admin.get("/api/v1/admin/health").json()
    assert report["worker"] == "healthy" and report["models_verified_at"]
    with Session(world["engine"]) as db, db.begin():
        db.get(ServiceReport, "worker").heartbeat_at = now() - timedelta(minutes=5)
    assert admin.get("/api/v1/admin/health").json()["worker"] == "unhealthy"
    metrics = admin.get("/api/v1/admin/metrics").json()
    assert metrics["buckets"] == [] and metrics["minimum_workspaces"] == 5
    assert world["client"]("owner0").get("/api/v1/admin/metrics").status_code == 403
