"""Review edits are validated as a complete batch before any change is saved."""

import hashlib
import random
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from stmtconv.config import Settings
from stmtconv.core.models import Statement, Transaction
from stmtconv.core.validate import validate
from stmtconv.errors import StmtconvError
from stmtconv.export.csv_writer import safe_text
from stmtconv.extract.service import persist, read_statements
from stmtconv.orders import store

HEADERS = [
    "Row ID",
    "Date",
    "Description",
    "Debit",
    "Credit",
    "Balance",
    "Page",
    "Engine",
    "Check",
    "Expected",
    "Difference",
    "Flags",
    "Fix Date",
    "Fix Description",
    "Fix Debit",
    "Fix Credit",
    "Fix Balance",
    "Action",
    "Note",
]


def digest(statement: Statement) -> str:
    return hashlib.sha256(statement.model_dump_json().encode()).hexdigest()


def write(settings: Settings, order_id: str) -> list[Path]:
    order = store.load(settings.workspace, order_id)
    store.require(order, {"needs_review", "reviewed"})
    paths = []
    for statement in read_statements(settings, order_id):
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "Review"
        sheet.append(HEADERS)
        for row in statement.transactions:
            sheet.append(
                [
                    row.id,
                    row.date,
                    safe_text(row.description),
                    row.debit,
                    row.credit,
                    row.balance,
                    row.page,
                    row.engine,
                    row.check.status,
                    row.check.expected,
                    row.check.difference,
                    ";".join(row.flags),
                    None,
                    None,
                    None,
                    None,
                    None,
                    "keep",
                    None,
                ]
            )
            if row.check.status == "MISMATCH" or row.flags:
                for cell in sheet[sheet.max_row]:
                    cell.fill = PatternFill(
                        "solid", fgColor="FFF2CC" if row.check.status == "MISMATCH" else "FCE4D6"
                    )
        sheet.freeze_panes = "A2"
        metadata = workbook.create_sheet("_Metadata")
        metadata.append([order_id, statement.id, digest(statement)])
        metadata.sheet_state = "hidden"
        issues = workbook.create_sheet("Issues")
        issues.append(["Flag"])
        for flag in statement.flags:
            issues.append([flag])
        path = store.child(
            store.root(settings.workspace, order_id), f"review/{statement.id}-review.xlsx"
        )
        temporary = path.with_suffix(".tmp.xlsx")
        workbook.save(temporary)
        temporary.replace(path)
        paths.append(path)
    return paths


def fix_money(value: object, negative: bool = False) -> Decimal | None:
    if value in {None, ""}:
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
            raise ValueError("nonnegative two-decimal money required")
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


def apply(settings: Settings, order_id: str) -> list[Statement]:
    started = perf_counter()
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"needs_review", "reviewed"})
        originals = read_statements(settings, order_id)
        changed: list[Statement] = []
        fixes = 0
        for original in originals:
            path = store.child(
                store.root(settings.workspace, order_id), f"review/{original.id}-review.xlsx"
            )
            workbook = load_workbook(path, data_only=False)
            if "_Metadata" not in workbook or list(workbook["_Metadata"].values)[0] != (
                order_id,
                original.id,
                digest(original),
            ):
                raise StmtconvError(
                    "REVIEW_STALE",
                    "Review workbook is stale or belongs to another statement.",
                    "Generate a fresh review workbook.",
                )
            sheet = workbook["Review"]
            if list(next(sheet.values)) != HEADERS:
                raise StmtconvError("REVIEW_COLUMNS", "Review column headings were changed.")
            existing = {row.id: row for row in original.transactions}
            seen: set[str] = set()
            rows: list[Transaction] = []
            result = original.model_copy(deep=True)
            local_fixes = 0
            for number, values in enumerate(list(sheet.values)[1:], 2):
                if all(v is None for v in values):
                    continue
                data = dict(zip(HEADERS, values, strict=True))
                row_id = str(data["Row ID"])
                if row_id not in existing or row_id in seen:
                    raise StmtconvError(
                        "REVIEW_ROW", f"Unknown or duplicate row ID at sheet row {number}."
                    )
                seen.add(row_id)
                action = data["Action"] or "keep"
                if action not in {"keep", "fix", "delete", "insert_after"}:
                    raise StmtconvError("REVIEW_ACTION", f"Invalid Action at sheet row {number}.")
                row = existing[row_id].model_copy(deep=True)
                if action == "delete":
                    fixes += 1
                    local_fixes += 1
                    result.review_history.append({"row_id": row_id, "action": "delete"})
                    continue
                if action == "insert_after":
                    rows.append(row)
                    row = row.model_copy(
                        update={
                            "id": hashlib.sha256(
                                f"{row_id}|insert|{digest(original)}".encode()
                            ).hexdigest()[:16],
                            "debit": None,
                            "credit": None,
                            "balance": None,
                            "flags": [],
                        },
                        deep=True,
                    )
                edited = False
                try:
                    for field in ["Date", "Description", "Debit", "Credit", "Balance"]:
                        value = data["Fix " + field]
                        if value is None or value == "":
                            continue
                        if action == "keep":
                            raise ValueError("choose fix or insert_after")
                        if field == "Date":
                            row.date = fix_date(value)
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
                            from stmtconv.core.dates import parse_date

                            _, flags = parse_date(
                                row.date.isoformat(),
                                "YMD",
                                original.summary.period_start,
                                original.summary.period_end,
                                allowance_days=settings.date_out_of_period_days,
                            )
                            row.flags.extend(flags)
                        elif field == "Description":
                            if (
                                not isinstance(value, str)
                                or not value.strip()
                                or value.startswith("=")
                            ):
                                raise ValueError("plain text required")
                            row.description = value.strip()
                            row.flags = [f for f in row.flags if f != "DESC_NUMERIC"]
                            if row.description.isdigit():
                                row.flags.append("DESC_NUMERIC")
                        else:
                            setattr(row, field.lower(), fix_money(value, field == "Balance"))
                            cleared = {"MONEY_" + field.upper() + "_UNPARSABLE"}
                            if field in {"Debit", "Credit"}:
                                cleared |= {"MONEY_MOVEMENT_MISSING", "MONEY_AMOUNT_UNPARSABLE"}
                            row.flags = [f for f in row.flags if f not in cleared]
                            if not any(f.startswith("MONEY_") for f in row.flags):
                                row.flags = [f for f in row.flags if f != "AMOUNT_UNPARSABLE"]
                        edited = True
                    if action == "insert_after" and (
                        not data["Fix Date"]
                        or not data["Fix Description"]
                        or (row.debit is None and row.credit is None)
                    ):
                        raise ValueError("insert needs date, description and amount")
                    if action == "fix" and not edited:
                        raise ValueError("fix needs at least one changed field")
                except (ValueError, TypeError) as exc:
                    raise StmtconvError(
                        "REVIEW_CELL",
                        f"Invalid fix at sheet row {number}.",
                        "Use dates, plain descriptions, nonnegative two-decimal numbers, or clear for blank money.",
                    ) from exc
                if edited:
                    row.fixed_by = "review"
                    fixes += 1
                    local_fixes += 1
                    result.review_history.append(
                        {"row_id": row_id, "action": str(action), "note": str(data["Note"] or "")}
                    )
                rows.append(row)
            if seen != set(existing):
                raise StmtconvError(
                    "REVIEW_MISSING", "Rows were removed from the sheet; use Action=delete instead."
                )
            result.transactions = rows
            result.manual_fixes += local_fixes
            if not any("DATE_ORDER_AMBIGUOUS" in t.flags for t in rows):
                result.flags = [f for f in result.flags if f != "DATE_ORDER_AMBIGUOUS"]
            changed.append(validate(result, settings.balance_tolerance))
        persist(settings, order_id, changed)
        order.manual_fixes += fixes
        order.timings["review"] = order.timings.get("review", 0) + perf_counter() - started
        order.spot_check = type(order.spot_check)()
        for fact, statement in zip(order.statements, changed, strict=True):
            fact.verdict = statement.verdict
            fact.rows = len(statement.transactions)
            fact.mismatches = sum(t.check.status == "MISMATCH" for t in statement.transactions)
        from stmtconv.orders.models import Status

        target: Status = (
            "needs_review"
            if any(s.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"} for s in changed)
            else "reviewed"
        )
        if order.status != target:
            store.transition(order, target)
    return changed


def sample(settings: Settings, order_id: str) -> list[Transaction]:
    randomizer = random.Random(order_id)
    rows: list[Transaction] = []
    for statement in read_statements(settings, order_id):
        selected = randomizer.sample(
            statement.transactions, min(settings.spot_check_rows, len(statement.transactions))
        )
        by_id = {
            t.id: t
            for t in [*selected, *(t for t in statement.transactions if t.fixed_by == "review")]
        }
        rows.extend(by_id.values())
    return rows


def record_spotcheck(
    settings: Settings, order_id: str, passed: bool, note: str = ""
) -> list[Transaction]:
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"needs_review", "reviewed"})
        rows = sample(settings, order_id)
        order.spot_check.sample_ids = [row.id for row in rows]
        order.spot_check.passed = passed
        order.spot_check.note = note
    return rows
