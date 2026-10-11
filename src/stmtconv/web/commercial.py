"""Server-owned account limits and conservative durable page reservations."""

import hashlib
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.errors import WebError
from stmtconv.web.models import (
    AiRun,
    Entitlement,
    Invitation,
    Job,
    Membership,
    Operation,
    PageReservation,
    SourceFile,
    now,
)
from stmtconv.web.repository import Json


def allowance(db: Session, config: HostedSettings, workspace: UUID) -> Json:
    record = db.get(Entitlement, workspace)
    if record:
        active = record.status == "active" and record.valid_until > now()
        return {
            "status": record.status if record.valid_until > now() else "expired",
            "processing_allowed": active,
            "page_limit": int(cast(int, record.limits["pages_per_month"])) if active else 0,
            "seat_limit": int(cast(int, record.limits["seats"])) if active else 0,
            "valid_until": record.valid_until.isoformat(),
        }
    return {
        "status": "development" if config.mode == "local" else "awaiting_activation",
        "processing_allowed": config.mode == "local",
        "page_limit": config.development_page_allowance if config.mode == "local" else 0,
        "seat_limit": config.development_seats if config.mode == "local" else 0,
        "valid_until": None,
    }


def period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def used_pages(db: Session, workspace: UUID, month: str | None = None) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(PageReservation.pages), 0)).where(
                PageReservation.workspace_id == workspace,
                PageReservation.period == (month or period()),
            )
        )
        or 0
    )


def usage_data(db: Session, config: HostedSettings, workspace: UUID) -> Json:
    limits = allowance(db, config, workspace)
    month = period()
    used = used_pages(db, workspace, month)
    pending = int(
        db.scalar(
            select(func.coalesce(func.sum(PageReservation.pages), 0)).where(
                PageReservation.workspace_id == workspace,
                PageReservation.period == month,
                PageReservation.settled.is_(False),
            )
        )
        or 0
    )
    seats = int(
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.workspace_id == workspace, Membership.active.is_(True))
        )
        or 0
    )
    return {
        **limits,
        "period": month,
        "pages_used": used - pending,
        "pages_reserved": pending,
        "pages_remaining": max(0, cast(int, limits["page_limit"]) - used),
        "active_seats": seats,
        "pending_invitations": pending_seats(db, workspace),
        "ai_charges_included": False,
        "inspection_reservation_max": config.job_pages,
    }


def pending_seats(db: Session, workspace: UUID, exclude: UUID | None = None) -> int:
    q = (
        select(func.count())
        .select_from(Invitation)
        .where(
            Invitation.workspace_id == workspace,
            Invitation.status == "pending",
            Invitation.expires_at > now(),
        )
    )
    if exclude:
        q = q.where(Invitation.id != exclude)
    return int(db.scalar(q) or 0)


def admit_seat(
    db: Session, config: HostedSettings, workspace: UUID, exclude: UUID | None = None
) -> None:
    limits = allowance(db, config, workspace)
    active = int(
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.workspace_id == workspace, Membership.active.is_(True))
        )
        or 0
    )
    if active + pending_seats(db, workspace, exclude) >= cast(int, limits["seat_limit"]):
        raise WebError(
            409,
            "SEAT_LIMIT",
            "Your team's allowance is full. Review usage or ask for a plan change.",
        )


def reserve_pages(
    db: Session, config: HostedSettings, job: Job, files: list[SourceFile], action: str
) -> None:
    # Caller holds the existing workspace lock; check and reservation are one transaction.
    limits = allowance(db, config, job.workspace_id)
    month = period()
    if not limits["processing_allowed"]:
        raise WebError(
            403, "PLAN_INACTIVE", "Processing access is inactive. Existing files remain available."
        )
    basis = hashlib.sha256(
        ":".join(sorted(str(f.id) + ":" + str(f.artifact_id) for f in files)).encode()
    ).hexdigest()
    record = db.scalar(
        select(PageReservation).where(
            PageReservation.workspace_id == job.workspace_id,
            PageReservation.job_id == job.id,
            PageReservation.period == month,
            PageReservation.source_digest == basis,
        )
    )
    if record is None:
        budget = config.job_pages
        if used_pages(db, job.workspace_id, month) + budget > cast(int, limits["page_limit"]):
            raise WebError(
                429,
                "PAGE_ALLOWANCE",
                "There isn't enough page allowance to inspect this job safely. Review usage or ask for a plan change.",
            )
        record = PageReservation(
            workspace_id=job.workspace_id,
            job_id=job.id,
            period=month,
            source_digest=basis,
            pages=budget,
        )
        db.add(record)
    if action == "extract" and not record.settled:
        measured = sum(len(f.pages) for f in files)
        if measured < 1 or measured > record.pages:
            raise WebError(
                409, "PAGE_BUDGET", "Inspection must finish within the reserved page budget."
            )
        record.pages = measured
        record.settled = True
    db.flush()


def cancel_processing(db: Session, workspace: UUID) -> None:
    # Publication checks current operation/run state. Cleanup receipts remain
    # separate; revocation never asserts an interrupted process erased its memory.
    db.execute(
        update(Operation)
        .where(
            Operation.workspace_id == workspace,
            Operation.action.in_(["intake", "extract"]),
            Operation.state.in_(["queued", "running", "cancel_requested"]),
        )
        .values(state="cancelled", error_code="PLAN_REVOKED", lease_hash=None, lease_until=None)
    )
    db.execute(
        update(AiRun)
        .where(AiRun.workspace_id == workspace, AiRun.state.in_(["queued", "running"]))
        .values(state="cancelled", error_code="PLAN_REVOKED")
    )
