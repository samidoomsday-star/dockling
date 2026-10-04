"""Deterministic CSV serialization; no monetary arithmetic via floats."""

import csv
import io
from decimal import Decimal

from stmtconv.catalog import ExportFormat
from stmtconv.core.models import Statement, Transaction
from stmtconv.errors import StmtconvError


def safe_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def money(value: Decimal | None) -> str:
    return format(value, ".2f") if value else ""


def cells(row: Transaction, date_format: str) -> dict[str, str]:
    amount = None if "AMOUNT_UNPARSABLE" in row.flags else row.amount
    return {
        "Date": row.date.strftime(date_format) if row.date else "",
        "Description": safe_text(row.description),
        "Debit": money(row.debit),
        "Credit": money(row.credit),
        "Amount": money(amount),
        "Balance": money(row.balance),
        "Payee": "",
        "Reference": row.id,
        "Check": row.check.status,
        "Flags": ";".join(row.flags),
        "Page": str(row.page),
        "Engine": row.engine,
        "Source file": safe_text(row.source_file),
        "Category": safe_text(row.category or ""),
    }


def serialize(
    statement: Statement,
    spec: ExportFormat,
    date_format: str,
    rows: list[Transaction] | None = None,
    bom: bool = False,
) -> bytes:
    if date_format not in spec.date_formats:
        raise StmtconvError(
            "EXPORT_DATE_FORMAT", "The selected date format is not allowed for this output."
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(spec.columns)
    for row in rows if rows is not None else statement.transactions:
        values = cells(row, date_format)
        if set(spec.columns) - set(values):
            raise StmtconvError("EXPORT_COLUMNS", "An output column has no defined value.")
        writer.writerow([values[column] for column in spec.columns])
    return output.getvalue().encode("utf-8-sig" if bom else "utf-8")
