"""Raw rows become normalized transactions without hiding parse failures."""

import hashlib
import re
from decimal import Decimal
from typing import Literal

from stmtconv.core.dates import DateOrder, parse_date, resolve_order
from stmtconv.core.models import RawRow, Statement, StatementSummary, Transaction
from stmtconv.core.money import parse_money


def assemble(rows: list[RawRow]) -> list[RawRow]:
    result: list[RawRow] = []
    for raw in rows:
        row = raw.model_copy(deep=True)
        amounts = any([row.debit, row.credit, row.amount, row.balance])
        if not row.date and row.description and not amounts and result:
            result[-1].description += " " + row.description
            result[-1].raw_text += "\n" + row.raw_text
        elif row.date or amounts:
            if not row.date and result:
                row.date = result[-1].date
                row.date_inherited = True
            result.append(row)
    return result


def normalize(
    statement_id: str,
    rows: list[RawRow],
    summary: StatementSummary,
    date_order: DateOrder = "auto",
    decimal_separator: str = ".",
    thousands_separator: str = ",",
    amount_style: Literal["separate_columns", "signed_single", "dr_cr_suffix"] = "separate_columns",
    formats: list[str] | None = None,
    allowance_days: int = 7,
    pages: list[int] | None = None,
) -> Statement:
    assembled = assemble(rows)
    order, statement_flags = resolve_order([r.date for r in assembled], date_order)
    transactions: list[Transaction] = []
    for index, row in enumerate(assembled):
        parsed_date, flags = parse_date(
            row.date, order, summary.period_start, summary.period_end, formats, allowance_days
        )
        description = re.sub(r"\s+", " ", row.description).strip(" \t|;:")
        if description.isdigit():
            flags.append("DESC_NUMERIC")
        values: dict[str, Decimal | None] = {}
        for name in ["debit", "credit", "balance", "amount"]:
            try:
                values[name] = parse_money(
                    getattr(row, name), decimal_separator, thousands_separator
                )
            except ValueError:
                values[name] = None
                flags.append("AMOUNT_UNPARSABLE")
        debit, credit = values["debit"], values["credit"]
        if amount_style != "separate_columns":
            amount = values["amount"]
            if amount is None:
                flags.append("AMOUNT_UNPARSABLE")
            else:
                signed = -amount if summary.direction == "liability" else amount
                debit = -signed if signed < 0 else None
                credit = signed if signed > 0 else None
        else:
            debit = abs(debit) if debit is not None else None
            credit = abs(credit) if credit is not None else None
            if debit is None and credit is None:
                flags.append("AMOUNT_UNPARSABLE")
        row_id = hashlib.sha256(
            f"{statement_id}|{row.source_file}|{row.page}|{index}".encode()
        ).hexdigest()[:16]
        transactions.append(
            Transaction(
                id=row_id,
                date=parsed_date,
                description=description,
                debit=debit,
                credit=credit,
                balance=values["balance"],
                source_file=row.source_file,
                page=row.page,
                engine=row.engine,
                raw_text=row.raw_text,
                date_inherited=row.date_inherited,
                flags=list(dict.fromkeys(flags)),
                fixed_by="ai" if row.engine == "ai" else None,
            )
        )
    return Statement(
        id=statement_id,
        summary=summary,
        transactions=transactions,
        flags=statement_flags,
        pages=pages or sorted({r.page for r in rows}),
    )
