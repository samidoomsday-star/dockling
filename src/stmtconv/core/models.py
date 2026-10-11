"""Pure domain records shared by extraction, validation, review and exporters."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

SourcePages = dict[
    Annotated[str, Field(min_length=1)], list[Annotated[int, Field(ge=1, strict=True)]]
]

Direction = Literal["asset", "liability"]
Verdict = Literal[
    "VERIFIED", "VERIFIED_BY_TOTALS", "VERIFIED_WITH_FIXES", "NEEDS_REVIEW", "UNVERIFIABLE"
]


class Domain(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_validator("*", mode="before")
    @classmethod
    def no_float_money(cls, value: object, info: ValidationInfo) -> object:
        if info.field_name in {
            "debit",
            "credit",
            "balance",
            "opening",
            "closing",
            "total_debits",
            "total_credits",
            "expected",
            "difference",
        } and isinstance(value, float):
            raise ValueError("financial fields require Decimal or exact strings")
        return value


class RawRow(Domain):
    date: str = ""
    description: str = ""
    debit: str = ""
    credit: str = ""
    amount: str = ""
    balance: str = ""
    source_file: str = ""
    page: int = Field(default=1, ge=1)
    engine: Literal["text", "docling", "ai"] = "text"
    raw_text: str = ""
    date_inherited: bool = False


class RowCheck(Domain):
    status: Literal["OK", "MISMATCH", "UNVERIFIED"] = "UNVERIFIED"
    expected: Decimal | None = None
    difference: Decimal | None = None


class Transaction(Domain):
    id: str
    date: date | None
    description: str
    debit: Decimal | None = Field(default=None, ge=0)
    credit: Decimal | None = Field(default=None, ge=0)
    balance: Decimal | None = None
    source_file: str
    page: int = Field(ge=1)
    engine: Literal["text", "docling", "ai"]
    raw_text: str
    fixed_by: Literal["review", "ai"] | None = None
    date_inherited: bool = False
    source_reviewed: bool = False
    flags: list[str] = Field(default_factory=list)
    check: RowCheck = Field(default_factory=RowCheck)
    category: str | None = None

    @property
    def amount(self) -> Decimal:
        return (self.credit or Decimal(0)) - (self.debit or Decimal(0))


class StatementSummary(Domain):
    account_mask: str | None = None
    account_key: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    opening: Decimal | None = None
    closing: Decimal | None = None
    total_debits: Decimal | None = None
    total_credits: Decimal | None = None
    currency: str = "USD"
    direction: Direction = "asset"


class Statement(Domain):
    id: str
    summary: StatementSummary
    transactions: list[Transaction]
    verdict: Verdict = "NEEDS_REVIEW"
    flags: list[str] = Field(default_factory=list)
    manual_fixes: int = 0
    review_history: list[dict[str, object]] = Field(default_factory=list)
    checks: dict[str, bool | None] = Field(default_factory=dict)
    pages: list[int] = Field(default_factory=list)
    summary_pages: list[int] = Field(default_factory=list)
    # Composite statements keep virtual pages above and qualified physical sources here.
    # Omit absent fields so legacy statement/review hashes remain unchanged.
    source_pages: SourcePages | None = Field(default=None, exclude_if=lambda value: value is None)
    source_summary_pages: SourcePages | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    timings: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, dict[str, object]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def qualified_coverage(self) -> Self:
        if self.source_pages is None:
            if self.source_summary_pages is not None:
                raise ValueError("Qualified summary pages require a source inventory")
            return self
        if not self.source_pages or any(
            not pages or len(pages) != len(set(pages)) for pages in self.source_pages.values()
        ):
            raise ValueError("Source inventory requires distinct physical pages")
        expected = {(source, page) for source, pages in self.source_pages.items() for page in pages}
        summaries = {
            (source, page)
            for source, pages in (self.source_summary_pages or {}).items()
            for page in pages
        }
        if summaries - expected:
            raise ValueError("Summary pages must belong to the exact source inventory")
        return self

    @property
    def debit_total(self) -> Decimal:
        return sum((t.debit or Decimal(0) for t in self.transactions), Decimal(0))

    @property
    def credit_total(self) -> Decimal:
        return sum((t.credit or Decimal(0) for t in self.transactions), Decimal(0))
