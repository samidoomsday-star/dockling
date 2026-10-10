"""Untrusted Excel adapter. Every cell is checked before shared commands execute."""

from io import BytesIO
from typing import Literal, cast
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from pydantic import ValidationError

from stmtconv.core.models import Statement
from stmtconv.errors import StmtconvError
from stmtconv.review.commands import ReviewEdit, RowChanges, fix_date, fix_money


def read_edits(data: bytes, statement: Statement, binding: list[object]) -> list[ReviewEdit]:
    from stmtconv.review.service import HEADERS

    try:
        with ZipFile(BytesIO(data)) as archive:
            items = archive.infolist()
            if len(items) > 500 or sum(i.file_size for i in items) > 64 * 1024**2:
                raise ValueError("Workbook expanded size")
            for item in items:
                if item.file_size > 100 * max(item.compress_size, 1):
                    raise ValueError("Workbook compression ratio")
                if "vba" in item.filename.lower() or "externallinks" in item.filename.lower():
                    raise ValueError("Workbook external content")
                if item.filename.endswith((".xml", ".rels")):
                    xml = archive.read(item)
                    if (
                        b"<!DOCTYPE" in xml.upper()
                        or b"<!ENTITY" in xml.upper()
                        or b'TargetMode="External"' in xml
                    ):
                        raise ValueError("Workbook external content")
        book = load_workbook(BytesIO(data), data_only=False, keep_links=False)
    except (BadZipFile, ValueError, KeyError) as exc:
        raise StmtconvError("REVIEW_CELL", "Use a bounded plain review workbook.") from exc
    try:
        if "_Metadata" not in book or list(book["_Metadata"].values)[0] != tuple(binding):
            raise StmtconvError(
                "REVIEW_STALE", "Review workbook is stale or belongs to another statement."
            )
        if "Review" not in book:
            raise StmtconvError("REVIEW_COLUMNS", "The Review sheet is required.")
        sheet = book["Review"]
        if (
            sheet.max_row > 10002
            or sheet.max_column != len(HEADERS)
            or list(next(sheet.values)) != HEADERS
        ):
            raise StmtconvError("REVIEW_COLUMNS", "Review column headings were changed.")
        existing = {row.id for row in statement.transactions}
        seen: set[str] = set()
        edits: list[ReviewEdit] = []
        for number, cells in enumerate(list(sheet.rows)[1:], 2):
            if all(c.value is None for c in cells):
                continue
            values = {name: cell.value for name, cell in zip(HEADERS, cells, strict=True)}
            row_id = str(values["Row ID"])
            if row_id not in existing or row_id in seen:
                raise StmtconvError(
                    "REVIEW_ROW", f"Unknown or duplicate row ID at sheet row {number}."
                )
            seen.add(row_id)
            action = values["Action"] or "keep"
            if action not in {"keep", "fix", "delete", "insert_after"}:
                raise StmtconvError("REVIEW_ACTION", f"Invalid Action at sheet row {number}.")
            changes: dict[str, object] = {}
            field = "Action"
            try:
                for field in ("Date", "Description", "Debit", "Credit", "Balance"):
                    cell = cells[HEADERS.index("Fix " + field)]
                    value = cell.value
                    if value is None or value == "":
                        continue
                    if cell.data_type == "f" or action in {"keep", "delete"}:
                        raise ValueError("Choose fix or insert_after with plain values")
                    if field == "Date":
                        changes["date"] = None if value == "clear" else fix_date(value).isoformat()
                    elif field == "Description":
                        changes["description"] = value
                    else:
                        amount = fix_money(value, field == "Balance")
                        changes[field.lower()] = None if amount is None else format(amount, ".2f")
                if action == "keep":
                    continue
                edits.append(
                    ReviewEdit(
                        statement_id=statement.id,
                        row_id=row_id,
                        action=cast(Literal["fix", "delete", "insert_after"], action),
                        changes=None if action == "delete" else RowChanges.model_validate(changes),
                        note=str(values["Note"] or ""),
                    )
                )
            except (ValueError, TypeError, ValidationError) as exc:
                raise StmtconvError(
                    "REVIEW_CELL", f"Invalid Fix {field} at sheet row {number}."
                ) from exc
        if seen != existing:
            raise StmtconvError(
                "REVIEW_MISSING", "Rows were removed from the workbook; use Action delete."
            )
        return edits
    finally:
        book.close()
