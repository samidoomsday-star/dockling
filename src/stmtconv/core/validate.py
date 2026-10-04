"""Direction-aware reconciliation is evidence, not proof of all source content."""

from decimal import Decimal

from stmtconv.core.models import RowCheck, Statement

BLOCKING = {
    "AMOUNT_UNPARSABLE",
    "DATE_ORDER_AMBIGUOUS",
    "YEAR_UNKNOWN",
    "DATE_UNPARSABLE",
    "DATE_OUT_OF_PERIOD",
    "PAGE_COVERAGE",
    "EMPTY_STATEMENT",
    "SOURCE_COVERAGE_UNKNOWN",
    "SUMMARY_UNPARSABLE",
    "AI_RESULT_UNTRUSTED",
}


def validate(statement: Statement, tolerance: Decimal, row_order: str = "auto") -> Statement:
    candidate = statement.model_copy(deep=True)
    if row_order == "reverse":
        candidate.transactions.reverse()
    elif row_order == "auto" and len(candidate.transactions) > 1:
        forward = validate(candidate, tolerance, "chronological")
        reverse = validate(
            candidate.model_copy(
                update={"transactions": list(reversed(candidate.transactions))}, deep=True
            ),
            tolerance,
            "chronological",
        )
        candidate = min(
            [forward, reverse],
            key=lambda s: (
                sum(t.check.status == "MISMATCH" for t in s.transactions),
                sum(v is False for v in s.checks.values()),
            ),
        )
        candidate.transactions.sort(key=lambda t: (t.date is None, t.date))
        return candidate
    candidate.flags = [f for f in candidate.flags if f not in {"PAGE_COVERAGE", "EMPTY_STATEMENT"}]
    summary = candidate.summary
    previous = summary.opening
    for row in candidate.transactions:
        expected = (
            None
            if previous is None or "AMOUNT_UNPARSABLE" in row.flags
            else previous + (row.amount if summary.direction == "asset" else -row.amount)
        )
        difference = (
            row.balance - expected if row.balance is not None and expected is not None else None
        )
        status = (
            "UNVERIFIED"
            if difference is None
            else "OK"
            if abs(difference) <= tolerance
            else "MISMATCH"
        )
        row.check = RowCheck(status=status, expected=expected, difference=difference)
        previous = row.balance if row.balance is not None else expected
    checks: dict[str, bool | None] = {}
    checks["closing"] = (
        None
        if previous is None or summary.closing is None
        else abs(previous - summary.closing) <= tolerance
    )
    for name, printed, computed in [
        ("debits", summary.total_debits, candidate.debit_total),
        ("credits", summary.total_credits, candidate.credit_total),
    ]:
        checks[name] = None if printed is None else abs(printed - computed) <= tolerance
    movement = candidate.credit_total - candidate.debit_total
    checks["movement"] = (
        None
        if summary.opening is None or summary.closing is None
        else abs(
            summary.opening
            + (movement if summary.direction == "asset" else -movement)
            - summary.closing
        )
        <= tolerance
    )
    seen: set[tuple[object, ...]] = set()
    for row in candidate.transactions:
        key = (row.date, row.amount, row.description)
        if key in seen and "POSSIBLE_DUPLICATE" not in row.flags:
            row.flags.append("POSSIBLE_DUPLICATE")
        seen.add(key)
    covered = {t.page for t in candidate.transactions} | set(candidate.summary_pages)
    if set(candidate.pages) - covered and "PAGE_COVERAGE" not in candidate.flags:
        candidate.flags.append("PAGE_COVERAGE")
    if not candidate.transactions and "EMPTY_STATEMENT" not in candidate.flags:
        candidate.flags.append("EMPTY_STATEMENT")
    candidate.checks = checks
    flags = set(candidate.flags) | {flag for t in candidate.transactions for flag in t.flags}
    if (
        flags & BLOCKING
        or any(t.check.status == "MISMATCH" for t in candidate.transactions)
        or any(value is False for value in checks.values())
    ):
        candidate.verdict = "NEEDS_REVIEW"
    elif checks["movement"] is True and checks["closing"] is True:
        if any(t.balance is not None for t in candidate.transactions):
            candidate.verdict = "VERIFIED"
        elif checks["debits"] is True and checks["credits"] is True:
            candidate.verdict = "VERIFIED_BY_TOTALS"
        else:
            candidate.verdict = "UNVERIFIABLE"
        if candidate.verdict != "UNVERIFIABLE" and (
            candidate.manual_fixes > 0
            or any(t.fixed_by == "review" for t in candidate.transactions)
        ):
            candidate.verdict = "VERIFIED_WITH_FIXES"
    else:
        candidate.verdict = "UNVERIFIABLE"
    return candidate
