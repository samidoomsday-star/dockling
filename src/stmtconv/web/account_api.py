"""Verified account onboarding, private notices/support and manual-invoice entitlement ledger."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from pydantic import Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.auth import is_admin
from stmtconv.web.commercial import allowance, usage_data
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import (
    AccountCommand,
    BillingEvidence,
    BillingInvoice,
    CommercialPlan,
    Entitlement,
    Event,
    Invitation,
    Membership,
    NoticeReceipt,
    ServiceRequest,
    User,
    Workspace,
    now,
)
from stmtconv.web.owner_api import Actor
from stmtconv.web.pipeline_api import Scope
from stmtconv.web.repository import Cursors, Json, replay
from stmtconv.web.schemas import Command


class WorkspaceCreate(Command):
    name: str = Field(min_length=1, max_length=80)


class PlanCommand(Command):
    name: str = Field(min_length=1, max_length=80)
    pages_per_month: int = Field(ge=1, le=10000)
    seats: int = Field(ge=1, le=100)
    monthly_amount: str = Field(pattern=r"^(0|[1-9][0-9]{0,5})\.[0-9]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    approved_for_customers: bool = False

    @field_validator("monthly_amount")
    @classmethod
    def positive(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("Use a positive exact amount")
        return value


class InvoiceCreate(Command):
    plan_id: UUID = Field(strict=False)
    days: int = Field(default=30, ge=1, le=366)


class EvidenceCommand(Command):
    expected_version: int = Field(ge=1)
    status: Literal["issued", "paid", "failed", "refunded", "cancelled"]
    reference: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{7,119}$")
    verified_evidence: bool


class RequestCreate(Command):
    kind: Literal["support", "plan", "privacy_export", "privacy_remove"]
    message: str = Field(min_length=1, max_length=500)


class RequestUpdate(Command):
    expected_version: int = Field(ge=1)
    status: Literal["answered", "closed"]
    response: str = Field(min_length=1, max_length=500)


class AllowanceRead(Command):
    status: Literal[
        "active", "refunded", "cancelled", "expired", "development", "awaiting_activation"
    ]
    processing_allowed: bool
    page_limit: int = Field(ge=0)
    seat_limit: int = Field(ge=0)
    valid_until: str | None


class UsageRead(AllowanceRead):
    period: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")
    pages_used: int = Field(ge=0)
    pages_reserved: int = Field(ge=0)
    pages_remaining: int = Field(ge=0)
    active_seats: int = Field(ge=0)
    pending_invitations: int = Field(ge=0)
    ai_charges_included: Literal[False]
    inspection_reservation_max: int = Field(ge=1, le=100)


class PlanRead(PlanCommand):
    id: UUID = Field(strict=False)


class PlanList(Command):
    items: list[PlanRead]


class OffersRead(PlanList):
    offers_enabled: bool


class InvoiceRead(Command):
    id: UUID = Field(strict=False)
    version: int = Field(ge=1)
    status: Literal["draft", "issued", "paid", "failed", "refunded", "cancelled"]
    plan_name: str
    amount: str = Field(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    valid_until: str
    created_at: str
    payment_method: Literal["manual_invoice"]


class BillingRead(Command):
    entitlement: AllowanceRead
    invoices: list[InvoiceRead]
    checkout_available: Literal[False]
    portal_available: Literal[False]
    mode: Literal["manual_invoice"]


class AdminBillingRead(Command):
    workspace_id: UUID = Field(strict=False)
    entitlement: AllowanceRead
    invoices: list[InvoiceRead]


class RequestRead(RequestCreate):
    id: UUID = Field(strict=False)
    status: Literal["open", "answered", "closed"]
    version: int = Field(ge=1)
    response: str | None
    created_at: str


class RequestsRead(Command):
    items: list[RequestRead]


class AdminRequestRead(RequestRead):
    workspace_id: UUID = Field(strict=False)


class AdminRequestsRead(Command):
    items: list[AdminRequestRead]


class InvitationRead(Command):
    id: UUID = Field(strict=False)
    email: str
    role: Literal["editor", "viewer"]
    status: Literal["pending", "accepted", "revoked", "expired"]
    expires_at: str


class InvitationsRead(Command):
    items: list[InvitationRead]


class NoticeRead(Command):
    id: UUID = Field(strict=False)
    action: str
    created_at: str
    read: bool


class NoticesRead(Command):
    items: list[NoticeRead]


class NoticeAcknowledged(Command):
    read: Literal[True]


class WorkspaceRead(Command):
    id: UUID = Field(strict=False)
    name: str
    role: Literal["owner", "editor", "viewer"]


class BillingWorkspaceRead(Command):
    id: UUID = Field(strict=False)
    name: str


class BillingWorkspacesRead(Command):
    items: list[BillingWorkspaceRead]


def invoice_json(db: Session, record: BillingInvoice) -> Json:
    plan = db.get(CommercialPlan, record.plan_id)
    assert plan is not None
    return {
        "id": str(record.id),
        "version": record.version,
        "status": record.status,
        "plan_name": plan.data["name"],
        "amount": plan.data["monthly_amount"],
        "currency": plan.data["currency"],
        "valid_until": record.valid_until.isoformat(),
        "created_at": record.at.isoformat(),
        "payment_method": "manual_invoice",
    }


def request_json(record: ServiceRequest) -> Json:
    return {
        "id": str(record.id),
        "kind": record.kind,
        "message": record.message,
        "status": record.status,
        "version": record.version,
        "response": record.response,
        "created_at": record.at.isoformat(),
    }


def register_accounts(
    app: FastAPI,
    config: HostedSettings,
    provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    actor: Actor,
    key: Callable[[Request], str],
    cursors: Cursors,
) -> None:
    Db = Annotated[Session, Depends(provider, scope="function")]

    def admin(db: Session, request: Request, write: bool = False) -> User:
        session, user = actor(db, request, write=write)
        if not is_admin(config, session, user):
            raise WebError(
                403,
                "ADMIN_MFA_REQUIRED",
                "Administrator access requires a fresh verified second-factor sign-in.",
            )
        return user

    def workspace_lock(db: Session, identifier: UUID) -> None:
        if not db.scalar(select(Workspace.id).where(Workspace.id == identifier).with_for_update()):
            raise missing()

    @app.post("/api/v1/workspaces", status_code=201, response_model=WorkspaceRead)
    def create_workspace(body: WorkspaceCreate, request: Request, db: Db) -> Json:
        session, user = actor(db, request, write=True)
        db.execute(select(User.id).where(User.id == user.id).with_for_update()).first()
        if not user.email_verified or not user.email:
            raise WebError(
                403,
                "VERIFIED_EMAIL_REQUIRED",
                "Verify your account email before creating a workspace.",
            )
        command_key = key(request)
        previous = db.scalar(
            select(AccountCommand).where(
                AccountCommand.actor_id == user.id, AccountCommand.key == command_key
            )
        )
        if previous and previous.name != body.name:
            raise WebError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "That request key was already used for another command.",
            )
        if previous:
            identifier = previous.workspace_id
        else:
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(Membership)
                    .where(Membership.user_id == user.id, Membership.role == "owner")
                )
                or 0
            )
            if count >= 3:
                raise WebError(
                    429,
                    "WORKSPACE_LIMIT",
                    "You can own three workspaces. Ask support before adding another.",
                )
            record = Workspace(name=body.name.strip())
            if not record.name:
                raise WebError(422, "NAME_REQUIRED", "Enter a workspace name.")
            db.add(record)
            db.flush()
            db.add(Membership(workspace_id=record.id, user_id=user.id, role="owner"))
            db.flush()
            db.add(Event(workspace_id=record.id, actor_id=user.id, action="workspace.created"))
            identifier = record.id
            db.add(
                AccountCommand(
                    actor_id=user.id, key=command_key, name=body.name, workspace_id=identifier
                )
            )
        member = db.scalar(
            select(Membership).where(
                Membership.workspace_id == identifier,
                Membership.user_id == user.id,
                Membership.active.is_(True),
            )
        )
        if member is None:
            raise missing()
        session.workspace_id = identifier
        workspace = db.get(Workspace, identifier)
        assert workspace
        return {"id": str(identifier), "name": workspace.name, "role": member.role}

    @app.get("/api/v1/usage", response_model=UsageRead)
    def usage(request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        return usage_data(db, config, ws)

    @app.get("/api/v1/billing", response_model=BillingRead)
    def billing(request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request, owner=True)
        records = db.scalars(
            select(BillingInvoice)
            .where(BillingInvoice.workspace_id == ws)
            .order_by(BillingInvoice.at.desc())
            .limit(100)
        )
        return {
            "entitlement": allowance(db, config, ws),
            "invoices": [invoice_json(db, r) for r in records],
            "checkout_available": False,
            "portal_available": False,
            "mode": "manual_invoice",
        }

    @app.get("/api/v1/plans", response_model=OffersRead)
    def plans(request: Request, db: Db) -> Json:
        scoped(db, request)
        records = (
            list(db.scalars(select(CommercialPlan).order_by(CommercialPlan.at.desc()).limit(100)))
            if config.commercial_offers_enabled
            else []
        )
        return {
            "items": [
                {"id": str(r.id), **r.data}
                for r in records
                if r.data.get("approved_for_customers") is True
            ],
            "offers_enabled": config.commercial_offers_enabled,
        }

    @app.post("/api/v1/billing/checkout")
    @app.post("/api/v1/billing/portal")
    def not_integrated(request: Request, db: Db) -> Json:
        scoped(db, request, write=True, owner=True)
        key(request)
        raise WebError(
            409,
            "MANUAL_BILLING",
            "Online payments are not enabled. Request a plan or invoice from the service owner.",
        )

    @app.get("/api/v1/invitations", response_model=InvitationsRead)
    def invitations(request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request, owner=True)
        rows = db.scalars(
            select(Invitation)
            .where(Invitation.workspace_id == ws)
            .order_by(Invitation.expires_at.desc())
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": str(i.id),
                    "email": i.email,
                    "role": i.role,
                    "status": "expired"
                    if i.status == "pending" and i.expires_at <= now()
                    else i.status,
                    "expires_at": i.expires_at.isoformat(),
                }
                for i in rows
            ]
        }

    @app.get("/api/v1/requests", response_model=RequestsRead)
    def requests(request: Request, db: Db) -> Json:
        ws, user = scoped(db, request)
        q = select(ServiceRequest).where(ServiceRequest.workspace_id == ws)
        member = db.scalar(
            select(Membership).where(Membership.workspace_id == ws, Membership.user_id == user.id)
        )
        if member is None or member.role != "owner":
            q = q.where(ServiceRequest.actor_id == user.id)
        return {
            "items": [
                request_json(r) for r in db.scalars(q.order_by(ServiceRequest.at.desc()).limit(100))
            ]
        }

    @app.post("/api/v1/requests", status_code=201, response_model=RequestRead)
    def request_help(body: RequestCreate, request: Request, db: Db) -> Json:
        session, user = actor(db, request, write=True)
        from stmtconv.web.repository import membership

        member = membership(db, session.workspace_id, user.id)
        ws = member.workspace_id
        workspace_lock(db, ws)
        if body.kind != "support" and member.role != "owner":
            raise WebError(
                403,
                "ROLE_DENIED",
                "A workspace owner must request a plan or workspace privacy action.",
            )

        def execute() -> Json:
            if (
                db.scalar(
                    select(func.count())
                    .select_from(ServiceRequest)
                    .where(
                        ServiceRequest.workspace_id == ws,
                        ServiceRequest.at > now() - timedelta(hours=1),
                    )
                )
                or 0
            ) >= 10:
                raise WebError(429, "REQUEST_LIMIT", "Please wait before sending another request.")
            record = ServiceRequest(
                workspace_id=ws, actor_id=user.id, kind=body.kind, message=body.message
            )
            db.add(record)
            db.flush()
            db.add(Event(workspace_id=ws, actor_id=user.id, action="request.received"))
            return request_json(record)

        return replay(
            db, ws, user.id, "request.create", key(request), body.model_dump(mode="json"), execute
        )

    @app.get("/api/v1/notices", response_model=NoticesRead)
    def notices(request: Request, db: Db) -> Json:
        ws, user = scoped(db, request)
        events = db.scalars(
            select(Event).where(Event.workspace_id == ws).order_by(Event.at.desc()).limit(50)
        )
        seen = set(
            db.scalars(select(NoticeReceipt.event_id).where(NoticeReceipt.actor_id == user.id))
        )
        return {
            "items": [
                {
                    "id": str(e.id),
                    "action": e.action,
                    "created_at": e.at.isoformat(),
                    "read": e.id in seen,
                }
                for e in events
            ]
        }

    @app.post("/api/v1/notices/{notice}/read", response_model=NoticeAcknowledged)
    def read_notice(notice: UUID, request: Request, db: Db) -> Json:
        session, user = actor(db, request, write=True)
        from stmtconv.web.repository import membership

        ws = membership(db, session.workspace_id, user.id).workspace_id
        workspace_lock(db, ws)
        if not db.scalar(select(Event.id).where(Event.id == notice, Event.workspace_id == ws)):
            raise missing()

        def execute() -> Json:
            if not db.scalar(
                select(NoticeReceipt.id).where(
                    NoticeReceipt.event_id == notice, NoticeReceipt.actor_id == user.id
                )
            ):
                db.add(NoticeReceipt(event_id=notice, actor_id=user.id))
            return {"read": True}

        return replay(db, ws, user.id, "notice.read:" + str(notice), key(request), {}, execute)

    @app.get("/api/v1/admin/plans", response_model=PlanList)
    def admin_plans(request: Request, db: Db) -> Json:
        admin(db, request)
        return {
            "items": [
                {"id": str(p.id), **p.data}
                for p in db.scalars(
                    select(CommercialPlan).order_by(CommercialPlan.at.desc()).limit(100)
                )
            ]
        }

    @app.get("/api/v1/admin/billing-workspaces", response_model=BillingWorkspacesRead)
    def billing_workspaces(request: Request, db: Db) -> Json:
        admin(db, request)
        from stmtconv.web.models import AdminSpace

        q = (
            select(Workspace)
            .where(Workspace.id.not_in(select(AdminSpace.workspace_id)))
            .order_by(Workspace.id)
            .limit(100)
        )
        return {"items": [{"id": str(w.id), "name": w.name} for w in db.scalars(q)]}

    @app.post("/api/v1/admin/plans", status_code=201, response_model=PlanRead)
    def create_plan(body: PlanCommand, request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        from stmtconv.web.owner_api import admin_space

        ws = admin_space(db, user)
        workspace_lock(db, ws)

        def execute() -> Json:
            if body.approved_for_customers and not config.commercial_offers_enabled:
                raise WebError(
                    409,
                    "OFFERS_DISABLED",
                    "Commercial offers need owner approval and explicit environment activation.",
                )
            record = CommercialPlan(actor_id=user.id, data=body.model_dump(mode="json"))
            db.add(record)
            db.flush()
            db.add(Event(workspace_id=ws, actor_id=user.id, action="plan.draft.created"))
            return {"id": str(record.id), **record.data}

        return replay(
            db, ws, user.id, "plan.create", key(request), body.model_dump(mode="json"), execute
        )

    @app.get("/api/v1/admin/workspaces/{workspace}/billing", response_model=AdminBillingRead)
    def admin_billing(workspace: UUID, request: Request, db: Db) -> Json:
        admin(db, request)
        if db.get(Workspace, workspace) is None:
            raise missing()
        return {
            "workspace_id": str(workspace),
            "entitlement": allowance(db, config, workspace),
            "invoices": [
                invoice_json(db, i)
                for i in db.scalars(
                    select(BillingInvoice)
                    .where(BillingInvoice.workspace_id == workspace)
                    .order_by(BillingInvoice.at.desc())
                    .limit(100)
                )
            ],
        }

    @app.post(
        "/api/v1/admin/workspaces/{workspace}/invoices", status_code=201, response_model=InvoiceRead
    )
    def create_invoice(workspace: UUID, body: InvoiceCreate, request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        workspace_lock(db, workspace)

        def execute() -> Json:
            plan = db.get(CommercialPlan, body.plan_id)
            if plan is None:
                raise missing()
            if config.mode == "production" and (
                not config.commercial_offers_enabled or not plan.data.get("approved_for_customers")
            ):
                raise WebError(
                    409, "OFFER_UNAPPROVED", "Approve the offer before issuing a customer invoice."
                )
            invoice = BillingInvoice(
                workspace_id=workspace,
                plan_id=plan.id,
                valid_until=now() + timedelta(days=body.days),
            )
            db.add(invoice)
            db.flush()
            db.add(Event(workspace_id=workspace, actor_id=user.id, action="invoice.draft.created"))
            return invoice_json(db, invoice)

        return replay(
            db,
            workspace,
            user.id,
            "invoice.create",
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.post(
        "/api/v1/admin/workspaces/{workspace}/invoices/{invoice}/evidence",
        response_model=InvoiceRead,
    )
    def evidence(
        workspace: UUID, invoice: UUID, body: EvidenceCommand, request: Request, db: Db
    ) -> Json:
        user = admin(db, request, True)
        workspace_lock(db, workspace)
        record = db.scalar(
            select(BillingInvoice).where(
                BillingInvoice.workspace_id == workspace, BillingInvoice.id == invoice
            )
        )
        if record is None:
            raise missing()

        def execute() -> Json:
            if record.version != body.expected_version:
                raise WebError(
                    409, "STALE_VERSION", "Refresh the invoice before recording another event."
                )
            allowed = {
                "draft": {"issued", "cancelled"},
                "issued": {"paid", "failed", "cancelled"},
                "failed": {"issued", "cancelled"},
                "paid": {"refunded", "cancelled"},
            }
            if body.status not in allowed.get(record.status, set()) or not body.verified_evidence:
                raise WebError(
                    409,
                    "PAYMENT_EVIDENCE",
                    "Verify the real event and follow the invoice's current state.",
                )
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                {"scope": "manual-evidence:" + body.reference},
            )
            if db.scalar(
                select(BillingEvidence.id).where(BillingEvidence.reference == body.reference)
            ):
                raise WebError(
                    409, "EVIDENCE_USED", "This evidence reference has already been recorded."
                )
            if body.status == "paid" and record.valid_until <= now():
                raise WebError(
                    409,
                    "INVOICE_EXPIRED",
                    "Create a current invoice; the access period has expired.",
                )
            entitlement = db.get(Entitlement, workspace)
            if body.status == "paid":
                if (
                    entitlement
                    and entitlement.status == "active"
                    and entitlement.valid_until > now()
                    and entitlement.invoice_id != invoice
                ):
                    raise WebError(
                        409,
                        "ACTIVE_PLAN",
                        "An active invoice already controls this workspace. End it before replacing it.",
                    )
                plan = db.get(CommercialPlan, record.plan_id)
                assert plan
                if entitlement is None:
                    entitlement = Entitlement(
                        workspace_id=workspace,
                        invoice_id=invoice,
                        status="active",
                        limits=plan.data,
                        valid_until=record.valid_until,
                    )
                    db.add(entitlement)
                else:
                    entitlement.invoice_id = invoice
                    entitlement.status = "active"
                    entitlement.limits = plan.data
                    entitlement.valid_until = record.valid_until
            elif (
                entitlement
                and entitlement.invoice_id == invoice
                and body.status in {"refunded", "cancelled"}
            ):
                entitlement.status = body.status
                from stmtconv.web.commercial import cancel_processing

                cancel_processing(db, workspace)
            record.status = body.status
            record.version += 1
            db.add(
                BillingEvidence(
                    workspace_id=workspace,
                    invoice_id=invoice,
                    actor_id=user.id,
                    version=record.version,
                    status=body.status,
                    reference=body.reference,
                )
            )
            db.add(Event(workspace_id=workspace, actor_id=user.id, action="invoice." + body.status))
            db.flush()
            return invoice_json(db, record)

        return replay(
            db,
            workspace,
            user.id,
            "invoice.evidence:" + str(invoice),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )

    @app.get("/api/v1/admin/requests", response_model=AdminRequestsRead)
    def admin_requests(request: Request, db: Db) -> Json:
        admin(db, request)
        return {
            "items": [
                {"workspace_id": str(r.workspace_id), **request_json(r)}
                for r in db.scalars(
                    select(ServiceRequest).order_by(ServiceRequest.at.desc()).limit(100)
                )
            ]
        }

    @app.post("/api/v1/admin/requests/{identifier}/response", response_model=RequestRead)
    def respond(identifier: UUID, body: RequestUpdate, request: Request, db: Db) -> Json:
        user = admin(db, request, True)
        record = db.get(ServiceRequest, identifier)
        if record is None:
            raise missing()
        workspace_lock(db, record.workspace_id)
        db.refresh(record)

        def execute() -> Json:
            if record.version != body.expected_version or record.status == "closed":
                raise WebError(409, "STALE_VERSION", "Refresh the request before responding.")
            record.status = body.status
            record.response = body.response
            record.version += 1
            db.add(
                Event(workspace_id=record.workspace_id, actor_id=user.id, action="request.answered")
            )
            return request_json(record)

        return replay(
            db,
            record.workspace_id,
            user.id,
            "request.response:" + str(identifier),
            key(request),
            body.model_dump(mode="json"),
            execute,
        )
