"""Anonymous operating signals and minimal component readiness; no customer content."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import ColumnElement

from stmtconv.config import HostedSettings
from stmtconv.web.auth import is_admin
from stmtconv.web.errors import WebError
from stmtconv.web.models import (
    AiAttempt,
    AiRun,
    BackupReceipt,
    Job,
    Operation,
    RestoreReceipt,
    ServiceReport,
    now,
)
from stmtconv.web.owner_api import Actor
from stmtconv.web.storage import ObjectStore


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str
    level: Literal["warning", "critical"]
    message: str


class OperationsRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["healthy", "attention"]
    checked_at: str
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    oldest_queue_seconds: int = Field(ge=0)
    recent_failures: int = Field(ge=0)
    pending_removals: int = Field(ge=0)
    failed_removals: int = Field(ge=0)
    uncertain_ai_attempts: int = Field(ge=0)
    pending_ai_cleanup: int = Field(ge=0)
    backup_created_at: str | None
    backup_expires_at: str | None
    restore_verified_at: str | None
    alerts: list[Signal]


class ComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["alive", "ready", "unavailable"]


def ready(db: Session, store: ObjectStore) -> bool:
    db.execute(text("SELECT 1"))
    report = db.get(ServiceReport, "worker")
    return bool(report and report.heartbeat_at > now() - timedelta(seconds=60) and store.healthy())


def snapshot(db: Session, store: ObjectStore, config: HostedSettings) -> OperationsRead:
    at = now()

    def count(column: InstrumentedAttribute[Any], *conditions: ColumnElement[bool]) -> int:
        return int(db.scalar(select(func.count(column)).where(*conditions)) or 0)

    queued = count(Operation.id, Operation.state == "queued")
    running = count(Operation.id, Operation.state.in_(["running", "cancel_requested"]))
    oldest = db.scalar(select(func.min(Operation.created_at)).where(Operation.state == "queued"))
    seconds = max(0, int((at - oldest).total_seconds())) if oldest else 0
    failures = count(
        Operation.id,
        Operation.state.in_(["failed", "uncertain"]),
        Operation.created_at > at - timedelta(minutes=30),
    )
    pending = count(Job.id, Job.deletion_state == "pending")
    failed = count(Job.id, Job.deletion_state == "partial")
    uncertain = count(AiAttempt.id, AiAttempt.state == "uncertain")
    cleanup = count(AiRun.id, AiRun.cleanup_done.is_(False))
    backup = db.scalar(select(BackupReceipt).order_by(BackupReceipt.created_at.desc()).limit(1))
    restored = db.scalar(
        select(RestoreReceipt)
        .join(BackupReceipt, RestoreReceipt.backup_id == BackupReceipt.id)
        .where(BackupReceipt.expires_at > at)
        .order_by(RestoreReceipt.verified_at.desc())
        .limit(1)
    )
    alerts = []

    def alert(code: str, message: str, *, critical: bool = False) -> None:
        alerts.append(
            Signal(code=code, level="critical" if critical else "warning", message=message)
        )

    if not ready(db, store):
        alert(
            "COMPONENT_UNAVAILABLE",
            "Check the database, private storage and worker heartbeat.",
            critical=True,
        )
    if seconds > config.queue_alert_seconds:
        alert("QUEUE_DELAY", "The conversion queue is older than the configured threshold.")
    if failures:
        alert(
            "RECENT_FAILURE", "Recent operations need review; do not automatically retry paid AI."
        )
    if failed:
        alert(
            "REMOVAL_FAILED",
            "Live removal failed. No complete-removal certificate should be issued.",
            critical=True,
        )
    elif pending:
        alert("REMOVAL_PENDING", "Live removals are pending; inspect their cleanup receipts.")
    if uncertain:
        alert("AI_UNCERTAIN", "Provider outcomes are uncertain; reservations remain held.")
    if cleanup:
        alert(
            "AI_CLEANUP_PENDING",
            "Private AI process cleanup is unverified. Keep removal fenced.",
            critical=True,
        )
    if (
        not backup
        or backup.created_at < at - timedelta(hours=config.backup_alert_hours)
        or backup.expires_at <= at
    ):
        alert(
            "BACKUP_MISSING_OR_STALE",
            "Create and verify an encrypted backup before enabling customer intake.",
            critical=True,
        )
    if not restored or restored.verified_at < at - timedelta(days=config.restore_alert_days):
        alert(
            "RESTORE_UNVERIFIED",
            "Run an isolated restore drill; a saved file alone does not prove recovery.",
            critical=True,
        )
    return OperationsRead(
        status="attention" if alerts else "healthy",
        checked_at=at.isoformat(),
        queued=queued,
        running=running,
        oldest_queue_seconds=seconds,
        recent_failures=failures,
        pending_removals=pending,
        failed_removals=failed,
        uncertain_ai_attempts=uncertain,
        pending_ai_cleanup=cleanup,
        backup_created_at=backup.created_at.isoformat() if backup else None,
        backup_expires_at=backup.expires_at.isoformat() if backup else None,
        restore_verified_at=restored.verified_at.isoformat() if restored else None,
        alerts=alerts,
    )


def register_operations(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    actor: Actor,
    store: ObjectStore,
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    @app.get("/api/v1/health/live", response_model=ComponentRead)
    def live() -> ComponentRead:
        return ComponentRead(status="alive")

    @app.get("/api/v1/health/ready", response_model=ComponentRead)
    def readiness(db: Db) -> JSONResponse:
        try:
            ok = ready(db, store)
        except Exception:
            ok = False
        return JSONResponse(
            {"status": "ready" if ok else "unavailable"}, status_code=200 if ok else 503
        )

    @app.get("/api/v1/admin/operations", response_model=OperationsRead)
    def operations(request: Request, db: Db) -> OperationsRead:
        session, user = actor(db, request, write=False)
        if not is_admin(config, session, user):
            raise WebError(
                403,
                "ADMIN_MFA_REQUIRED",
                "Sign in with a fresh second factor to use service tools.",
            )
        return snapshot(db, store, config)
