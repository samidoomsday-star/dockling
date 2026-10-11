"""Real scoped operations status, restoration evidence privileges and intake admission."""

import asyncio
from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from test_foundation import create

from stmtconv.web.database import database
from stmtconv.web.models import BackupReceipt, Job, Operation, RestoreReceipt, ServiceReport, now


def test_anonymous_readiness_mfa_and_no_operational_identifiers(world, monkeypatch):
    client = world["client"]("owner0")
    assert client.get("/api/v1/health/live").json() == {"status": "alive"}
    assert client.get("/api/v1/health/ready").status_code == 503
    for role in ("owner0", "editor0", "viewer0", "admin-no-mfa", "outsider"):
        assert world["client"](role).get("/api/v1/admin/operations").status_code == 403
    admin = world["client"]("admin")
    report = admin.get("/api/v1/admin/operations")
    assert report.status_code == 200
    assert {a["code"] for a in report.json()["alerts"]} >= {
        "COMPONENT_UNAVAILABLE",
        "BACKUP_MISSING_OR_STALE",
        "RESTORE_UNVERIFIED",
    }
    private = create(
        world,
        body={
            "name": "Fictional PRIVATE document marker",
            "currency": "USD",
            "date_order": "auto",
            "outputs": ["csv"],
        },
    )
    assert private["id"] not in report.text and "PRIVATE document" not in report.text
    with Session(world["engine"]) as db, db.begin():
        db.add(
            ServiceReport(
                name="worker",
                heartbeat_at=now(),
                models_verified_at=now(),
                model_digest="a" * 64,
                version="synthetic",
            )
        )
        backup = BackupReceipt(
            sha256="b" * 64,
            created_at=now(),
            expires_at=now() + timedelta(days=7),
            objects=1,
            bytes=100,
            schema_version="0012_operations",
        )
        db.add(backup)
        db.flush()
        db.add(RestoreReceipt(backup_id=backup.id, seconds=3, checks={"synthetic": True}))
    assert client.get("/api/v1/health/ready").json() == {"status": "ready"}
    report = admin.get("/api/v1/admin/operations").json()
    assert report["status"] == "healthy"
    assert report["alerts"] == []
    assert "sha256" not in report and "checks" not in report
    monkeypatch.setattr(world["app"].state.broker.store, "healthy", lambda: False)
    assert client.get("/api/v1/health/ready").status_code == 503


def test_queue_partial_removal_and_stale_backup_alerts(world):
    private = create(world)
    with Session(world["engine"]) as db, db.begin():
        job = db.get(Job, UUID(private["id"]))
        job.deletion_state = "partial"
        db.add(
            Operation(
                workspace_id=world["workspaces"][0],
                job_id=job.id,
                input_revision=1,
                action="close",
                state="queued",
                created_at=now() - timedelta(minutes=5),
            )
        )
        db.add(
            BackupReceipt(
                sha256="c" * 64,
                created_at=now() - timedelta(days=2),
                expires_at=now() - timedelta(days=1),
                objects=0,
                bytes=100,
                schema_version="0012_operations",
            )
        )
    report = world["client"]("admin").get("/api/v1/admin/operations").json()
    codes = {a["code"] for a in report["alerts"]}
    assert {
        "QUEUE_DELAY",
        "REMOVAL_FAILED",
        "BACKUP_MISSING_OR_STALE",
        "RESTORE_UNVERIFIED",
    } <= codes
    assert report["oldest_queue_seconds"] >= 300 and report["failed_removals"] == 1
    assert private["id"] not in str(report)


def test_api_cannot_forge_or_erase_operator_receipts(world):
    engine = database(world["config"])
    try:
        for sql in (
            "INSERT INTO web_backup_receipts DEFAULT VALUES",
            "DELETE FROM web_backup_receipts",
            "INSERT INTO web_restore_receipts DEFAULT VALUES",
            "UPDATE web_restore_receipts SET seconds=0",
        ):
            with pytest.raises(ProgrammingError, match="42501"):
                with Session(engine) as db, db.begin():
                    db.execute(text(sql))
    finally:
        engine.dispose()


def test_expired_archive_cannot_back_a_current_restore_receipt(world):
    with Session(world["engine"]) as db, db.begin():
        expired = BackupReceipt(
            sha256="d" * 64,
            created_at=now() - timedelta(days=8),
            expires_at=now() - timedelta(days=1),
            objects=0,
            bytes=100,
            schema_version="0012_operations",
        )
        current = BackupReceipt(
            sha256="e" * 64,
            created_at=now(),
            expires_at=now() + timedelta(days=7),
            objects=0,
            bytes=100,
            schema_version="0012_operations",
        )
        db.add_all([expired, current])
        db.flush()
        db.add(RestoreReceipt(backup_id=expired.id, seconds=3, checks={"synthetic": True}))
    report = world["client"]("admin").get("/api/v1/admin/operations").json()
    assert report["restore_verified_at"] is None
    assert "RESTORE_UNVERIFIED" in {a["code"] for a in report["alerts"]}
    assert "BACKUP_MISSING_OR_STALE" not in {a["code"] for a in report["alerts"]}


def test_early_body_denial_has_privacy_security_headers(world):
    c = world["client"]("owner0")
    response = c.post("/api/v1/jobs", content=b"x" * 65537)
    assert response.status_code == 413
    for key, value in {
        "cache-control": "private, no-store",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=(), microphone=(), geolocation=()",
    }.items():
        assert response.headers[key] == value
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


def test_concurrent_slow_body_admission_bounded_and_slot_released(world):
    # Hold every configured slot in real ASGI body reads, then prove the next
    # request fails safely and normal access resumes after those readers finish.
    async def check():
        gate = asyncio.Event()
        started = 0

        async def body():
            nonlocal started
            started += 1
            yield b"{"
            await gate.wait()
            yield b"}"

        transport = httpx.ASGITransport(app=world["app"])
        async with httpx.AsyncClient(transport=transport, base_url=world["config"].base_url) as c:
            tasks = [
                asyncio.create_task(c.post("/api/v1/jobs", content=body()))
                for _ in range(world["config"].api_concurrency)
            ]
            for _ in range(100):
                if started == len(tasks):
                    break
                await asyncio.sleep(0.01)
            assert started == len(tasks)
            busy = await c.get("/api/v1/health/live")
            assert busy.status_code == 503
            assert busy.json()["code"] == "SERVICE_BUSY"
            assert busy.headers["cache-control"] == "private, no-store"
            gate.set()
            await asyncio.gather(*tasks)
            assert (await c.get("/api/v1/health/live")).json() == {"status": "alive"}

    asyncio.run(check())
