"""PostgreSQL records; private child foreign keys always include workspace identity."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "web_users"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Workspace(Base):
    __tablename__ = "web_workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class Membership(Base):
    __tablename__ = "web_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('owner','editor','viewer')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("web_workspaces.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("web_users.id"))
    role: Mapped[str] = mapped_column(String(12))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class WebSession(Base):
    __tablename__ = "web_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("web_users.id"))
    workspace_id: Mapped[UUID | None] = mapped_column(ForeignKey("web_workspaces.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mfa_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Base):
    __tablename__ = "web_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        CheckConstraint("revision >= 1"),
        CheckConstraint(
            "status IN ('created','intake_done','extracted','needs_review','reviewed','exported','delivered','closed','failed')"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("web_workspaces.id"), index=True)
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("web_users.id"))
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="created")
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    currency: Mapped[str] = mapped_column(String(3))
    options: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    deletion_state: Mapped[str] = mapped_column(String(12), default="active")


class Event(Base):
    __tablename__ = "web_events"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "job_id"], ["web_jobs.workspace_id", "web_jobs.id"]),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("web_workspaces.id"), index=True)
    job_id: Mapped[UUID | None]
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("web_users.id"))
    action: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int | None]
    code: Mapped[str | None] = mapped_column(String(80))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Invitation(Base):
    __tablename__ = "web_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('editor','viewer')"),
        CheckConstraint("status IN ('pending','accepted','revoked','expired')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("web_workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(12))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="pending")


class Idempotency(Base):
    __tablename__ = "web_idempotency"
    __table_args__ = (UniqueConstraint("workspace_id", "actor_id", "action", "key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("web_workspaces.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("web_users.id"))
    action: Mapped[str] = mapped_column(String(150))
    key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, object]] = mapped_column(JSONB)


class Artifact(Base):
    __tablename__ = "web_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "job_id"], ["web_jobs.workspace_id", "web_jobs.id"]),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    job_id: Mapped[UUID]
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int]
    kind: Mapped[str] = mapped_column(String(40))
    bytes: Mapped[int] = mapped_column(BigInteger)


class Operation(Base):
    __tablename__ = "web_operations"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "job_id"], ["web_jobs.workspace_id", "web_jobs.id"]),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    job_id: Mapped[UUID]
    input_revision: Mapped[int]
    state: Mapped[str] = mapped_column(String(20), default="queued")
    action: Mapped[str] = mapped_column(String(40))
    lease_generation: Mapped[int] = mapped_column(default=0)
