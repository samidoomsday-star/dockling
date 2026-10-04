"""Typed order records; credentials and document passwords have no fields here."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal[
    "created",
    "intake_done",
    "extracted",
    "needs_review",
    "reviewed",
    "exported",
    "delivered",
    "closed",
    "failed",
]
Output = Literal["excel", "qb_csv3", "qb_csv4", "xero_csv", "csv", "ofx"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Event(Record):
    status: Status
    at: datetime


class PageFact(Record):
    page: int = Field(ge=1)
    kind: Literal["text", "scanned", "blank"]
    rotation: int = 0


class FileFact(Record):
    name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: list[PageFact]
    kind: Literal["pdf", "image"]
    password_protected: bool = False
    work_file: str


class StatementFact(Record):
    id: str
    file: str
    pages: list[int]
    profile: str
    account_mask: str | None = None
    verdict: str = "NEEDS_REVIEW"
    rows: int = 0
    mismatches: int = 0
    engines: dict[str, str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class SpotCheck(Record):
    sample_ids: list[str] = Field(default_factory=list)
    passed: bool | None = None
    note: str = ""
    skipped: bool = False
    revision: str | None = None


class Order(Record):
    order_id: str = Field(pattern=r"^\d{8}-(fiverr|upwork|direct|test)-[a-z0-9]{8}$")
    created_at: datetime
    platform: Literal["fiverr", "upwork", "direct", "test"] = "direct"
    client_alias: str = Field(default="", max_length=40)
    package: str = "basic"
    addons: list[str] = Field(default_factory=list)
    document_type: Literal["statement", "invoice"] = "statement"
    operator: str = "owner"
    outputs: list[Output] = Field(default=["excel", "csv"])
    date_order: Literal["auto", "DMY", "MDY", "YMD"] = "auto"
    output_date_format: str = "%m/%d/%Y"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    categorize: bool = False
    merge: bool = False
    account_group: str | None = None
    account_confirmed: bool = False
    merge_issues: list[dict[str, object]] = Field(default_factory=list)
    ai_consent: Literal["none", "granted"] = "none"
    ai_consent_note: str = ""
    show_full_account: bool = False
    status: Status = "created"
    status_history: list[Event] = Field(default_factory=list)
    files: list[FileFact] = Field(default_factory=list)
    statements: list[StatementFact] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)
    manual_fixes: int = 0
    spot_check: SpotCheck = Field(default_factory=SpotCheck)
    error_code: str | None = None
    deleted_at: datetime | None = None
    deletion_certificate: dict[str, object] | None = None
    exported_unverified: bool = False
    export_hashes: dict[str, str] = Field(default_factory=dict)
    export_revision: str | None = None
    ai_pages_used: int = 0
    ai_provider_binding: str | None = None
    deletion_pending: bool = False
    deletion_inventory: list[dict[str, str]] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)
    pages_by_kind: dict[str, int] = Field(default_factory=dict)


TRANSITIONS: dict[Status, set[Status]] = {
    "created": {"intake_done", "failed"},
    "intake_done": {"extracted", "failed"},
    "extracted": {"needs_review", "reviewed", "failed"},
    "needs_review": {"reviewed", "failed"},
    "reviewed": {"needs_review", "exported", "failed"},
    "exported": {"delivered", "failed"},
    "delivered": {"closed", "failed"},
    "closed": set(),
    "failed": {"closed"},
}
