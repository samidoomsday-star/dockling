"""Actual PDF/S3/PG pipeline, lease fences, quotas and private source routes."""

import base64
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from conftest import validate_response
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from test_foundation import create

from stmtconv.config import load_settings, load_worker_settings
from stmtconv.demo import generate
from stmtconv.web.models import Artifact, Job, Membership, Operation, SourceFile, Workspace, now
from stmtconv.web.pipeline import compute
from stmtconv.web.worker import LeasedPostgres

with tempfile.TemporaryDirectory() as directory:
    PDF = generate(Path(directory), count=2)[0].read_bytes()


def upload(c, job, data=PDF, revision=1, name="Fictional statement.pdf"):
    return c.post(
        f"/api/v1/jobs/{job}/files",
        content=data,
        headers={
            "Content-Type": "application/octet-stream",
            "X-File-Name": name,
            "X-Expected-Revision": str(revision),
            "X-Synthetic-Confirmed": "true",
        },
    )


@pytest.fixture
def worker(world):
    cfg = load_worker_settings(Path(".local-saas/worker.env"))
    url = make_url(cfg.database_url.get_secret_value()).set(
        host="127.0.0.1", port=55432, database="dockling_test"
    )
    engine = create_engine(url, hide_parameters=True)
    yield LeasedPostgres(engine)
    engine.dispose()


def run(world, worker, tmp_path, token=None):
    token = token or uuid4().hex + uuid4().hex
    task = worker.claim(token)
    assert task
    broker = world["app"].state.broker

    def call(action, **values):
        return broker.call(
            {
                "operation": str(task.id),
                "generation": task.generation,
                "token": token,
                "action": action,
                **values,
            }
        )

    documents = {
        str(f.id): base64.b64decode(
            call(
                "read",
                artifact=str(
                    (f.normalized_id or f.original_id)
                    if task.action == "intake"
                    else f.normalized_id
                ),
            )["data"]
        )
        for f in task.files
    }
    passwords = call("passwords")["passwords"]
    result = compute(task, documents, passwords, tmp_path, load_settings(), 40)
    for a in result.artifacts:
        call("stage", artifact=str(a.id), kind=a.kind, data=base64.b64encode(a.data).decode())
    assert worker.publish(task, token, result.record)
    return task, result


def test_actual_upload_intake_conversion_and_private_sources(world, worker, tmp_path):
    job = create(world)
    c = world["client"]("owner0")
    jid = job["id"]
    original = upload(c, jid)
    assert original.status_code == 200, original.text
    validate_response("File", original.json())
    fid = original.json()["id"]
    assert original.json()["revision"] == 2
    assert c.get(f"/api/v1/jobs/{jid}/files/{fid}/download").content == PDF
    queued = c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    assert queued.status_code == 202, queued.text
    validate_response("Operation", queued.json())
    run(world, worker, tmp_path)
    inspected = c.get(f"/api/v1/jobs/{jid}").json()
    assert inspected["revision"] == 3 and inspected["status"] == "intake_done"
    image = c.get(f"/api/v1/jobs/{jid}/files/{fid}/pages/1")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert image.headers["cache-control"] == "private, no-store"
    queued = c.post(
        f"/api/v1/jobs/{jid}/operations", json={"expected_revision": 3, "action": "extract"}
    )
    assert queued.status_code == 202, queued.text
    run(world, worker, tmp_path)
    result = c.get(f"/api/v1/jobs/{jid}").json()
    assert (
        result["revision"] == 4
        and result["status"] == "needs_review"
        and not result["source_checked"]
    )
    rows = c.get(f"/api/v1/jobs/{jid}/rows?limit=1").json()
    validate_response("RowList", rows)
    assert len(rows["items"]) == 1 and rows["next_cursor"]
    assert rows["items"][0]["file_id"] == fid
    other = c.get(f"/api/v1/jobs/{jid}/rows", params={"cursor": rows["next_cursor"]}).json()
    assert len(other["items"]) == 1 and other["next_cursor"] is None
    assert c.get(f"/api/v1/jobs/{jid}/statements").json()["items"][0]["rows"] == 2
    assert c.post(f"/api/v1/jobs/{jid}/exports", json={"expected_revision": 4}).status_code == 409


@pytest.mark.parametrize("name", ["owner1", "editor1", "viewer1", "admin"])
def test_every_pipeline_read_denies_foreign_job(world, name):
    jid = create(world)["id"]
    owner = world["client"]("owner0")
    fid = upload(owner, jid).json()["id"]
    foreign = world["client"](name)
    for path in [
        "files",
        "rows",
        "statements",
        "operations",
        f"files/{fid}/download",
        f"files/{fid}/pages/1",
        f"operations/{uuid4()}",
    ]:
        assert foreign.get(f"/api/v1/jobs/{jid}/{path}").status_code == 404, path
    assert foreign.post(
        f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2}
    ).status_code == (403 if name == "viewer1" else 404)


def test_viewer_csrf_size_type_and_synthetic_confirmation(world):
    jid = create(world)["id"]
    assert upload(world["client"]("viewer0"), jid).status_code == 403
    c = world["client"]("owner0")
    c.headers["X-CSRF-Token"] = "invalid"
    assert upload(c, jid).status_code == 403
    c = world["client"]("owner0")
    assert upload(c, jid, b"<html>untrusted</html>").status_code == 422
    assert upload(c, jid, b"x" * (world["config"].upload_bytes + 1)).status_code == 413
    c.headers["X-Synthetic-Confirmed"] = "false"
    r = c.post(
        f"/api/v1/jobs/{jid}/files",
        content=PDF,
        headers={"X-File-Name": "test.pdf", "X-Expected-Revision": "1"},
    )
    assert r.status_code == 422
    assert c.get(f"/api/v1/jobs/{jid}/files").json()["items"] == []


def test_upload_replay_changed_payload_and_concurrent_enqueue(world):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    a = upload(c, jid)
    b = upload(c, jid)
    assert a.json() == b.json()
    assert upload(c, jid, name="Different.pdf").status_code == 409

    def queue(_):
        return world["client"]("owner0").post(
            f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2}
        )

    results = list(ThreadPoolExecutor(4).map(queue, range(4)))
    assert [r.status_code for r in results].count(202) == 1
    assert [r.status_code for r in results].count(409) == 3


def test_cancel_revocation_and_expired_generation_fence(world, worker):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid)
    operation = c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2}).json()
    token = uuid4().hex
    task = worker.claim(token)
    assert task
    with Session(world["engine"]) as db, db.begin():
        db.get(Operation, task.id).lease_until = now() - timedelta(seconds=1)
    next_token = uuid4().hex
    new = worker.claim(next_token)
    assert new and new.generation == task.generation + 1
    assert not worker.heartbeat(task, token, "inspecting", 0)
    assert not worker.publish(task, token, {"state": "failed", "code": "SHOULD_NOT_PUBLISH"})
    cancelled = c.post(
        f"/api/v1/jobs/{jid}/operations/{operation['id']}/cancel", json={"expected_revision": 2}
    )
    assert cancelled.status_code == 202
    assert not worker.publish(new, next_token, {"state": "failed", "code": "SHOULD_NOT_PUBLISH"})
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 2


def test_revoke_actor_blocks_claim_and_publication(world, worker):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid)
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    token = uuid4().hex
    task = worker.claim(token)
    assert task
    with Session(world["engine"]) as db, db.begin():
        m = db.scalar(
            select(Membership).where(
                Membership.workspace_id == world["workspaces"][0],
                Membership.user_id == world["users"]["owner0"],
            )
        )
        m.active = False
    assert not worker.publish(task, token, {"state": "failed", "code": "REVOKED"})
    with pytest.raises(ValueError):
        world["app"].state.broker.call(
            {
                "operation": str(task.id),
                "generation": task.generation,
                "token": token,
                "action": "passwords",
            }
        )


def test_broker_foreign_artifact_and_forged_capability_denied(world, worker):
    c = world["client"]("owner0")
    jid = create(world)["id"]
    upload(c, jid)
    foreign = world["client"]("owner1")
    other = create(world, "owner1")["id"]
    upload(foreign, other)
    with Session(world["engine"]) as db:
        artifact = db.scalar(select(SourceFile).where(SourceFile.job_id == UUID(other))).artifact_id
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    token = uuid4().hex
    task = worker.claim(token)
    assert task
    broker = world["app"].state.broker
    for values in [
        {"token": token, "artifact": str(artifact)},
        {"token": "forged", "artifact": str(task.files[0].original_id)},
    ]:
        with pytest.raises(ValueError):
            broker.call(
                {
                    "operation": str(task.id),
                    "generation": task.generation,
                    "action": "read",
                    **values,
                }
            )
    with worker.engine.connect() as connection:
        with pytest.raises(ProgrammingError):
            connection.execute(text("SELECT * FROM web_files"))


def test_encrypted_pdf_password_memory_only(world, worker, tmp_path):
    encrypted = generate(tmp_path / "encrypted", count=2, password="synthetic-password")[
        0
    ].read_bytes()
    jid = create(world)["id"]
    c = world["client"]("owner0")
    fid = upload(c, jid, encrypted).json()["id"]
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    _, result = run(world, worker, tmp_path)
    assert result.record["state"] == "awaiting_input"
    unlocked = c.post(
        f"/api/v1/jobs/{jid}/files/{fid}/unlock",
        json={"expected_revision": 2, "password": "synthetic-password"},
    )
    assert unlocked.status_code == 202, unlocked.text
    run(world, worker, tmp_path)
    assert c.get(f"/api/v1/jobs/{jid}").json()["status"] == "intake_done"
    with Session(world["engine"]) as db:
        for model in [Operation, Job]:
            for record in db.scalars(select(model)):
                assert "synthetic-password" not in str(record.__dict__)
    assert world["app"].state.broker.passwords.values == {}


def test_reorder_atomicity_and_storage_quota(world):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    first = upload(c, jid).json()
    c.headers["Idempotency-Key"] = str(uuid4())
    second = upload(c, jid, revision=2, name="Second.pdf").json()
    ordered = c.put(
        f"/api/v1/jobs/{jid}/file-order",
        json={"expected_revision": 3, "file_ids": [second["id"], first["id"]]},
    )
    assert ordered.status_code == 200, ordered.text
    assert [f["id"] for f in c.get(f"/api/v1/jobs/{jid}/files").json()["items"]] == [
        second["id"],
        first["id"],
    ]
    c.headers["Idempotency-Key"] = str(uuid4())
    assert (
        c.put(
            f"/api/v1/jobs/{jid}/file-order",
            json={"expected_revision": 4, "file_ids": [first["id"], first["id"]]},
        ).status_code
        == 422
    )
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 4


def test_two_encrypted_files_keep_completed_intake_and_wrong_password_safe(world, worker, tmp_path):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    files = []
    for index in range(2):
        password = f"fictional-password-{index}"
        data = generate(tmp_path / str(index), count=2, password=password)[0].read_bytes()
        c.headers["Idempotency-Key"] = str(uuid4())
        files.append(upload(c, jid, data, index + 1, f"Encrypted{index}.pdf").json()["id"])
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 3})
    _, result = run(world, worker, tmp_path)
    assert result.record["state"] == "awaiting_input"
    for password in ("wrong-password", "fictional-password-0"):
        c.headers["Idempotency-Key"] = str(uuid4())
        assert (
            c.post(
                f"/api/v1/jobs/{jid}/files/{files[0]}/unlock",
                json={"expected_revision": 3, "password": password},
            ).status_code
            == 202
        )
        _, result = run(world, worker, tmp_path)
        assert result.record["state"] == "awaiting_input"
    inspected = c.get(f"/api/v1/jobs/{jid}/files").json()["items"]
    assert inspected[0]["pages"] == 1 and not inspected[0]["password_required"]
    assert inspected[1]["password_required"] and inspected[1]["pages"] == 0
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 4
    assert c.get(f"/api/v1/jobs/{jid}/files/{files[0]}/pages/1").status_code == 200
    c.headers["Idempotency-Key"] = str(uuid4())
    assert (
        c.post(
            f"/api/v1/jobs/{jid}/files/{files[1]}/unlock",
            json={"expected_revision": 4, "password": "fictional-password-1"},
        ).status_code
        == 202
    )
    run(world, worker, tmp_path)
    assert c.get(f"/api/v1/jobs/{jid}").json()["status"] == "intake_done"
    assert [f["pages"] for f in c.get(f"/api/v1/jobs/{jid}/files").json()["items"]] == [1, 1]


def test_removal_revision_and_retry_exhaustion_fence(world, worker):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid)
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    for attempt in range(3):
        token = uuid4().hex
        task = worker.claim(token)
        assert task and task.generation == attempt + 1
        with Session(world["engine"]) as db, db.begin():
            db.get(Operation, task.id).lease_until = now() - timedelta(seconds=1)
    assert worker.claim(uuid4().hex) is None
    assert c.get(f"/api/v1/jobs/{jid}/operations/{task.id}").json()["state"] == "failed"
    assert not worker.publish(task, token, {"state": "succeeded", "files": []})
    c.post(
        f"/api/v1/jobs/{jid}/operations",
        json={"expected_revision": 2, "action": "retry", "retry_operation_id": str(task.id)},
    )
    token = uuid4().hex
    task = worker.claim(token)
    assert task
    with Session(world["engine"]) as db, db.begin():
        db.get(Job, UUID(jid)).deletion_state = "pending"
    assert not worker.heartbeat(task, token, "inspecting", 0)
    assert not worker.publish(task, token, {"state": "succeeded", "files": []})


def test_signature_is_quarantined_and_page_limits_precede_render(world, tmp_path):
    from stmtconv.errors import StmtconvError
    from stmtconv.web.pipeline import bounded_pdf

    corrupt = tmp_path / "invalid.pdf"
    corrupt.write_bytes(b"%PDF-1.7\ninvalid")
    with pytest.raises(StmtconvError, match="cannot be opened"):
        bounded_pdf(corrupt, 40)
    many = generate(tmp_path / "many", count=3, rows_per_page=1)[0]
    with pytest.raises(StmtconvError) as error:
        bounded_pdf(many, 2)
    assert error.value.code == "PAGE_LIMIT"


def test_storage_failure_rolls_back_inventory_and_reap_preserves_original(world, monkeypatch):
    from stmtconv.web.database import PostgresUnitOfWork
    from stmtconv.web.errors import WebError
    from stmtconv.web.maintenance import reap

    store = world["app"].state.broker.store
    jid = create(world)["id"]
    c = world["client"]("owner0")

    def unavailable(*args):
        raise WebError(503, "STORAGE_UNAVAILABLE", "Private storage is unavailable.")

    with monkeypatch.context() as patch:
        patch.setattr(store, "write", unavailable)
        assert upload(c, jid).status_code == 503
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 1
    assert c.get(f"/api/v1/jobs/{jid}/files").json()["items"] == []
    c.headers["Idempotency-Key"] = str(uuid4())
    file = upload(c, jid).json()
    orphan = "uploads/" + str(uuid4()) + "/" + str(uuid4())
    store.client.put_object(Bucket=store.bucket, Key=orphan, Body=b"synthetic orphan")
    counts, _ = reap(store, PostgresUnitOfWork(world["engine"]), min_age=timedelta(seconds=0))
    assert counts["deleted"] >= 1
    assert c.get(f"/api/v1/jobs/{jid}/files/{file['id']}/download").content == PDF
    with Session(world["engine"]) as db:
        assert db.scalar(select(Artifact).where(Artifact.job_id == UUID(jid))).state == "active"


def test_parser_ipc_is_bounded_json_and_digest_stable(world, worker, tmp_path):
    from stmtconv.web.worker import decode_result, encode_result

    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid)
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    run(world, worker, tmp_path)
    c.post(f"/api/v1/jobs/{jid}/operations", json={"expected_revision": 3, "action": "extract"})
    task, first = run(world, worker, tmp_path)
    assert decode_result(encode_result(first)).record == first.record
    with pytest.raises((ValueError, UnicodeError)):
        decode_result(b"\x80\x04pickle-is-not-accepted")
    broker = world["app"].state.broker
    with Session(world["engine"]) as db:
        sources = {
            str(f.id): broker.store.verified(db.get(Artifact, f.normalized_id)) for f in task.files
        }
    second = compute(task, sources, {}, tmp_path, load_settings(), 40)
    assert second.record["digest"] == first.record["digest"]


def test_page_quota_captured_and_enforced_before_render(world, worker, tmp_path, monkeypatch):
    from stmtconv.errors import StmtconvError

    monkeypatch.setattr(world["config"], "job_pages", 1)
    jid = create(world)["id"]
    c = world["client"]("owner0")
    data = generate(tmp_path / "pages", count=3, rows_per_page=1)[0].read_bytes()
    upload(c, jid, data)
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    token = uuid4().hex
    task = worker.claim(token)
    assert task and task.page_limit == 1
    # Changing a future workspace limit cannot expand this already-reserved task.
    monkeypatch.setattr(world["config"], "job_pages", 40)
    with pytest.raises(StmtconvError) as error:
        compute(task, {str(task.files[0].id): data}, {}, tmp_path, load_settings(), 100)
    assert error.value.code == "PAGE_LIMIT"
    assert worker.publish(task, token, {"state": "failed", "code": "PAGE_LIMIT"})
    assert c.get(f"/api/v1/jobs/{jid}").json()["revision"] == 2


def test_invoice_and_oversized_image_rejected(world, worker, tmp_path):
    from PIL import Image
    from reportlab.pdfgen.canvas import Canvas

    from stmtconv.errors import StmtconvError
    from stmtconv.web.pipeline import bounded_pdf

    invoice = tmp_path / "invoice.pdf"
    canvas = Canvas(str(invoice))
    canvas.drawString(30, 700, "INVOICE Total due: 10.00")
    canvas.save()
    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid, invoice.read_bytes())
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    task = worker.claim(uuid4().hex)
    with pytest.raises(StmtconvError) as error:
        compute(
            task, {str(task.files[0].id): invoice.read_bytes()}, {}, tmp_path, load_settings(), 40
        )
    assert error.value.code == "INTAKE_DOCUMENT_TYPE"
    image = tmp_path / "large.png"
    with Image.new("1", (5001, 4000)) as picture:
        picture.save(image)
    with pytest.raises(StmtconvError) as error:
        bounded_pdf(image, 40)
    assert error.value.code == "IMAGE_LIMIT"


def test_stage_rechecks_membership_after_waiting_for_workspace_lock(world, worker):
    jid = create(world)["id"]
    c = world["client"]("owner0")
    upload(c, jid)
    c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
    token = uuid4().hex
    task = worker.claim(token)
    broker = world["app"].state.broker
    reached = threading.Event()

    def marker(connection, cursor, statement, parameters, context, executemany):
        if "web_workspaces" in statement and "FOR UPDATE" in statement:
            reached.set()

    event.listen(world["app"].state.engine, "before_cursor_execute", marker)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(world["engine"]) as db, db.begin():
                db.scalar(
                    select(Workspace).where(Workspace.id == task.workspace_id).with_for_update()
                )
                future = pool.submit(
                    broker.call,
                    {
                        "operation": str(task.id),
                        "generation": task.generation,
                        "token": token,
                        "action": "stage",
                        "artifact": str(uuid4()),
                        "kind": "normalized",
                        "data": base64.b64encode(b"synthetic stage").decode(),
                    },
                )
                assert reached.wait(3)
                member = db.scalar(
                    select(Membership).where(
                        Membership.workspace_id == task.workspace_id,
                        Membership.user_id == world["users"]["owner0"],
                    )
                )
                member.active = False
            with pytest.raises(ValueError):
                future.result(timeout=5)
    finally:
        event.remove(world["app"].state.engine, "before_cursor_execute", marker)
    with Session(world["engine"]) as db:
        assert len(list(db.scalars(select(Artifact).where(Artifact.job_id == UUID(jid))))) == 1


def test_database_file_fk_and_preview_reject_wrong_parent(world, worker, tmp_path):
    c = world["client"]("owner0")
    jobs = [create(world)["id"], create(world)["id"]]
    files = []
    for jid in jobs:
        c.headers["Idempotency-Key"] = str(uuid4())
        files.append(upload(c, jid).json()["id"])
        c.post(f"/api/v1/jobs/{jid}/intake", json={"expected_revision": 2})
        run(world, worker, tmp_path)
    with Session(world["engine"]) as db:
        other = db.get(SourceFile, UUID(files[1]))
        other_normalized, other_preview = other.normalized_id, other.previews["1"]
    with pytest.raises(ProgrammingError) as rejected, Session(world["engine"]) as db, db.begin():
        db.get(SourceFile, UUID(files[0])).normalized_id = other_normalized
        db.flush()
    assert rejected.value.orig.args[0]["C"] == "23503"
    with Session(world["engine"]) as db, db.begin():
        db.get(SourceFile, UUID(files[0])).previews = {"1": other_preview}
    assert c.get(f"/api/v1/jobs/{jobs[0]}/files/{files[0]}/pages/1").status_code == 404
