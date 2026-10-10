"""Pure, whole-batch review commands shared by the browser and Excel adapters."""

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stmtconv.config import Settings
from stmtconv.core.dates import parse_date
from stmtconv.core.models import Statement, Transaction
from stmtconv.core.validate import validate
from stmtconv.errors import StmtconvError


class RowChanges(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    date: str | None = Field(default=None, max_length=10)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    debit: str | None = Field(default=None, max_length=24)
    credit: str | None = Field(default=None, max_length=24)
    balance: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def complete_validation(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply a changed field")
        for name in self.model_fields_set:
            value = getattr(self, name)
            if name == "date" and value is not None:
                fix_date(value)
            elif name == "description":
                if (
                    value is None
                    or not value.strip()
                    or value.startswith("=")
                    or any(ord(c) < 32 for c in value)
                ):
                    raise ValueError("Use visible plain description text")
            elif name in {"debit", "credit", "balance"} and value is not None:
                if not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,2})?", value):
                    raise ValueError("Use exact two-decimal money or null to clear")
                fix_money(value, name == "balance")
        return self


class ReviewEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    statement_id: str = Field(min_length=1, max_length=100)
    row_id: str = Field(min_length=1, max_length=100)
    action: Literal["fix", "delete", "insert_after"]
    changes: RowChanges | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def action_fields(self) -> Self:
        if (self.action == "delete") != (self.changes is None):
            raise ValueError("Fix/insert requires changes; delete must not carry changes")
        return self


def fix_money(value: object, negative: bool = False) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise ValueError("use numeric money")
    if isinstance(value, str) and value.strip() == "clear":
        return None
    try:
        parsed = Decimal(str(value))
        if (
            not parsed.is_finite()
            or (parsed < 0 and not negative)
            or parsed != parsed.quantize(Decimal("0.01"))
        ):
            raise ValueError("two-decimal money required")
        return parsed
    except InvalidOperation as exc:
        raise ValueError("invalid money") from exc


def fix_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("use an Excel date or YYYY-MM-DD")


def apply_edits(
    originals: list[Statement], edits: list[ReviewEdit], settings: Settings
) -> list[Statement]:
    """Return new records only after the entire command batch is valid."""
    indexed = {s.id: s for s in originals}
    if len(indexed) != len(originals):
        raise StmtconvError("REVIEW_STATEMENTS", "Statement identities are not unique.")
    by_row: dict[tuple[str, str], ReviewEdit] = {}
    for command in edits:
        key = command.statement_id, command.row_id
        if (
            key in by_row
            or command.statement_id not in indexed
            or not any(t.id == command.row_id for t in indexed[command.statement_id].transactions)
        ):
            raise StmtconvError("REVIEW_ROW", "Unknown, duplicate or foreign review row.")
        by_row[key] = command
    results = []
    for original in originals:
        result = original.model_copy(deep=True)
        rows: list[Transaction] = []
        for source in original.transactions:
            row = source.model_copy(deep=True)
            edit = by_row.get((original.id, row.id))
            if edit is None:
                rows.append(row)
                continue
            result.manual_fixes += 1
            result.review_history.append(
                {"row_id": row.id, "action": edit.action, "note": edit.note}
            )
            if edit.action == "delete":
                continue
            assert edit.changes is not None
            if edit.action == "insert_after":
                rows.append(row)
                row = row.model_copy(
                    update={
                        "id": hashlib.sha256(
                            f"{row.id}|insert|{hashlib.sha256(original.model_dump_json().encode()).hexdigest()}".encode()
                        ).hexdigest()[:16],
                        "debit": None,
                        "credit": None,
                        "balance": None,
                        "flags": [],
                    },
                    deep=True,
                )
            for name in edit.changes.model_fields_set:
                value = getattr(edit.changes, name)
                if name == "date":
                    row.date = fix_date(value) if value is not None else None
                    row.flags = [
                        f
                        for f in row.flags
                        if f
                        not in {
                            "DATE_ORDER_AMBIGUOUS",
                            "DATE_UNPARSABLE",
                            "YEAR_UNKNOWN",
                            "DATE_OUT_OF_PERIOD",
                        }
                    ]
                    if row.date is None:
                        row.flags.append("DATE_UNPARSABLE")
                    else:
                        _, flags = parse_date(
                            row.date.isoformat(),
                            "YMD",
                            original.summary.period_start,
                            original.summary.period_end,
                            allowance_days=settings.date_out_of_period_days,
                        )
                        row.flags.extend(flags)
                elif name == "description":
                    row.description = str(value).strip()
                    row.flags = [f for f in row.flags if f != "DESC_NUMERIC"]
                    if row.description.isdigit():
                        row.flags.append("DESC_NUMERIC")
                else:
                    setattr(row, name, fix_money(value, name == "balance"))
                    cleared = {"MONEY_" + name.upper() + "_UNPARSABLE"}
                    if name in {"debit", "credit"}:
                        cleared |= {"MONEY_MOVEMENT_MISSING", "MONEY_AMOUNT_UNPARSABLE"}
                    row.flags = [f for f in row.flags if f not in cleared]
                    if not any(f.startswith("MONEY_") for f in row.flags):
                        row.flags = [f for f in row.flags if f != "AMOUNT_UNPARSABLE"]
            if edit.action == "insert_after" and (
                row.date is None
                or "date" not in edit.changes.model_fields_set
                or "description" not in edit.changes.model_fields_set
                or row.debit is None
                and row.credit is None
            ):
                raise StmtconvError(
                    "REVIEW_INSERT", "An inserted row needs date, description and an amount."
                )
            row.fixed_by = "review"
            rows.append(row)
        result.transactions = rows
        if edits:
            for row in rows:
                row.source_reviewed = False
        if not any("DATE_ORDER_AMBIGUOUS" in t.flags for t in rows):
            result.flags = [f for f in result.flags if f != "DATE_ORDER_AMBIGUOUS"]
        if len(rows) > 10000:
            raise StmtconvError("ROW_LIMIT", "The reviewed statement has too many rows.")
        results.append(validate(result, settings.balance_tolerance))
    return results
