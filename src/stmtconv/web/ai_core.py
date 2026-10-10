"""Pure minimized cell preparation and atomic, source-bound AI response application."""

import json
from copy import deepcopy
from decimal import Decimal
from typing import cast

from stmtconv.config import Settings
from stmtconv.core.models import Statement
from stmtconv.core.validate import validate
from stmtconv.errors import StmtconvError
from stmtconv.extract.ai_engine import Rows
from stmtconv.extract.service import version
from stmtconv.privacy.mask import table_text
from stmtconv.review.commands import RowChanges, fix_date, fix_money
from stmtconv.web.pipeline import digest
from stmtconv.web.workflow import domains


def pages(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for s in domains(records):
        for row in s.transactions:
            key = digest([s.id, row.source_file, row.page])
            if key not in result:
                result[key] = {
                    "key": key,
                    "statement_id": s.id,
                    "file_id": row.source_file,
                    "page": row.page,
                    "row_ids": [],
                }
            cast(list[str], result[key]["row_ids"]).append(row.id)
    return result


def minimized(records: list[dict[str, object]], key: str, names: list[str]) -> str:
    selected = pages(records).get(key)
    if selected is None:
        raise StmtconvError("AI_PAGE_CHANGED", "Choose a current page with transaction cells.")
    statement = next(s for s in domains(records) if s.id == selected["statement_id"])
    rows = []
    for row in statement.transactions:
        if row.id not in cast(list[str], selected["row_ids"]):
            continue
        rows.append(
            {
                "date": row.date.isoformat() if row.date else "",
                "description": table_text(row.description, names),
                "debit": format(row.debit, ".2f") if row.debit is not None else "",
                "credit": format(row.credit, ".2f") if row.credit is not None else "",
                "amount": "",
                "balance": format(row.balance, ".2f") if row.balance is not None else "",
            }
        )
    if not 0 < len(rows) <= 1000:
        raise StmtconvError("AI_TABLE_LIMIT", "Use at most 1000 transaction rows per page.")
    value = table_text(json.dumps({"rows": rows}, ensure_ascii=False), names)
    if len(value.encode()) > 100_000:
        raise StmtconvError("AI_TABLE_LIMIT", "This page's minimized cells are too large.")
    return (
        "Keep these existing rows in the same order and count. Return dates as YYYY-MM-DD and exact decimal money strings; do not add or remove rows. Only transaction cells follow:\n"
        + value
    )


def apply_results(
    records: list[dict[str, object]], results: dict[str, Rows], settings: Settings, names: list[str]
) -> list[dict[str, object]]:
    cloned = deepcopy(records)
    inventory = pages(records)
    for key, response in results.items():
        page = inventory[key]
        record = next(
            r for r in cloned if cast(dict[str, object], r["domain"])["id"] == page["statement_id"]
        )
        statement = Statement.model_validate(record["domain"])
        chosen = [r for r in statement.transactions if r.id in cast(list[str], page["row_ids"])]
        if len(response.rows) != len(chosen):
            raise StmtconvError(
                "AI_ROW_COUNT", "AI changed the row count; review manually instead."
            )
        for row, cell in zip(chosen, response.rows, strict=True):
            if cell.amount:
                raise StmtconvError("AI_OUTPUT", "Use separate debit and credit columns.")
            try:
                change = RowChanges(
                    date=cell.date or None,
                    description=table_text(cell.description, names),
                    debit=cell.debit or None,
                    credit=cell.credit or None,
                    balance=cell.balance or None,
                )
                row.date = fix_date(change.date) if change.date else None
                row.description = change.description or ""
                row.debit = fix_money(change.debit)
                row.credit = fix_money(change.credit)
                row.balance = fix_money(change.balance, True)
            except ValueError:
                raise StmtconvError(
                    "AI_OUTPUT", "AI returned unsupported transaction cells; no edits were applied."
                ) from None
            row.engine, row.fixed_by, row.source_reviewed = "ai", "ai", False
            # The raw source/provenance stays unchanged. Rebuild parse flags for edited cells.
            row.flags = [
                f
                for f in row.flags
                if not f.startswith(("MONEY_", "DATE_"))
                and f not in {"AMOUNT_UNPARSABLE", "YEAR_UNKNOWN", "DESC_NUMERIC"}
            ]
            if row.date is None:
                row.flags.append("DATE_UNPARSABLE")
            if row.debit is None and row.credit is None:
                row.flags.append("AMOUNT_UNPARSABLE")
            if row.date and statement.summary.period_start and statement.summary.period_end:
                from datetime import timedelta

                allowance = timedelta(days=settings.date_out_of_period_days)
                if (
                    not statement.summary.period_start - allowance
                    <= row.date
                    <= statement.summary.period_end + allowance
                ):
                    row.flags.append("DATE_OUT_OF_PERIOD")
        statement = validate(statement, Decimal(settings.balance_tolerance))
        record["domain"] = statement.model_dump(mode="json")
        record["version"] = version([statement])
    # Every edit invalidates the previous complete source attestations.
    for record in cloned:
        statement = Statement.model_validate(record["domain"])
        for row in statement.transactions:
            row.source_reviewed = False
        record["domain"] = statement.model_dump(mode="json")
    return cloned
