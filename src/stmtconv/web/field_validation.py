"""Private, owner-recorded field observations; no inferred accuracy or import success."""

from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from stmtconv.web.schemas import Output

Status = Literal["not_run", "passed", "failed"]


class ImportObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output: Output
    status: Status = "not_run"
    destination_version: str | None = Field(default=None, min_length=1, max_length=80)
    rows_imported: int | None = Field(default=None, ge=0, le=100000)
    amounts_and_signs_checked: bool = False
    dates_checked: bool = False
    duplicate_behavior_checked: bool = False

    @model_validator(mode="after")
    def observed_import(self) -> Self:
        if self.status == "passed" and (
            not self.destination_version
            or self.rows_imported is None
            or not self.amounts_and_signs_checked
            or not self.dates_checked
            or not self.duplicate_behavior_checked
        ):
            raise ValueError("A passed import requires actual destination and value checks")
        return self


class FieldRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    layout_code: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,39}$")
    data_kind: Literal["synthetic", "permitted_field"] = "synthetic"
    permission_confirmed: bool = False
    permission_record_retained_privately: bool = False
    documents: int = Field(ge=1, le=1000)
    physical_pages: int = Field(ge=1, le=100000)
    expected_rows: int = Field(ge=0, le=100000)
    extracted_rows: int = Field(ge=0, le=100000)
    source_checked_rows: int = Field(ge=0, le=100000)
    exact_rows: int = Field(ge=0, le=100000)
    financial_reconciliation: Status = "not_run"
    queue_seconds: Decimal | None = Field(default=None, ge=0, le=604800)
    conversion_seconds: Decimal | None = Field(default=None, ge=0, le=604800)
    source_review_seconds: Decimal | None = Field(default=None, ge=0, le=604800)
    peak_worker_mib: int | None = Field(default=None, ge=1, le=1048576)
    host_cost_usd: Decimal | None = Field(default=None, ge=0, le=1000000)
    storage_cost_usd: Decimal | None = Field(default=None, ge=0, le=1000000)
    provider_cost_usd: Decimal | None = Field(default=None, ge=0, le=1000000)
    support_minutes: Decimal | None = Field(default=None, ge=0, le=1000000)
    labor_usd_per_hour: Decimal | None = Field(default=None, ge=0, le=1000000)
    allocated_costs_confirmed: bool = False
    imports: list[ImportObservation] = Field(min_length=6, max_length=6)

    @field_validator(
        "host_cost_usd",
        "storage_cost_usd",
        "provider_cost_usd",
        "labor_usd_per_hour",
        mode="before",
    )
    @classmethod
    def exact_money(cls, value: object) -> object:
        if isinstance(value, (float, bool)):
            raise ValueError("Record monetary decimals as exact text")
        return value

    @model_validator(mode="after")
    def evidence_consistency(self) -> Self:
        if self.physical_pages < self.documents:
            raise ValueError("Each document must account for physical pages")
        if self.data_kind == "permitted_field" and not (
            self.permission_confirmed and self.permission_record_retained_privately
        ):
            raise ValueError("Real field samples require permission retained privately")
        if self.source_checked_rows > self.expected_rows or self.exact_rows > min(
            self.source_checked_rows, self.extracted_rows
        ):
            raise ValueError("Source match counts must be bounded by checked and extracted rows")
        if {x.output for x in self.imports} != {
            "excel",
            "csv",
            "qb_csv3",
            "qb_csv4",
            "xero_csv",
            "ofx",
        }:
            raise ValueError("Record each of the six output formats exactly once")
        if any(
            x.status == "passed" and x.rows_imported != self.expected_rows for x in self.imports
        ):
            raise ValueError("Passed imports must preserve the expected row count")
        return self


def observations(run: FieldRun) -> dict[str, object]:
    fully_checked = run.source_checked_rows == run.expected_rows
    exact = (
        fully_checked
        and run.expected_rows > 0
        and run.extracted_rows == run.expected_rows == run.exact_rows
    )
    expenses = [run.host_cost_usd, run.storage_cost_usd, run.provider_cost_usd]
    labor = (
        (run.support_minutes + run.source_review_seconds / Decimal(60))
        * run.labor_usd_per_hour
        / Decimal(60)
        if run.support_minutes is not None
        and run.source_review_seconds is not None
        and run.labor_usd_per_hour is not None
        else None
    )
    complete_cost = (
        run.allocated_costs_confirmed and all(x is not None for x in expenses) and labor is not None
    )
    total = sum((x for x in expenses if x is not None), Decimal(0)) + (labor or Decimal(0))
    return {
        "scope": "owner_recorded_field_observations",
        "automated_accuracy_certification": False,
        "all_expected_rows_source_checked": fully_checked,
        "recorded_all_rows_exact": exact,
        "financial_reconciliation": run.financial_reconciliation,
        "passed_imports": sum(x.status == "passed" for x in run.imports),
        "failed_imports": sum(x.status == "failed" for x in run.imports),
        "unrun_imports": sum(x.status == "not_run" for x in run.imports),
        "allocated_costs_complete": complete_cost,
        "allocated_total_usd": str(total) if complete_cost else None,
        "allocated_cost_per_document_usd": str(total / Decimal(run.documents))
        if complete_cost
        else None,
        "allocated_cost_per_page_usd": str(total / Decimal(run.physical_pages))
        if complete_cost
        else None,
        "review_seconds_per_document": str(run.source_review_seconds / Decimal(run.documents))
        if run.source_review_seconds is not None
        else None,
    }
