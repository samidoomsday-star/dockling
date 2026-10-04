from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from stmtconv.core.dates import parse_date, resolve_order
from stmtconv.core.models import RawRow, StatementSummary
from stmtconv.core.money import parse_money
from stmtconv.core.normalize import assemble, normalize
from stmtconv.core.validate import validate


@pytest.mark.parametrize(
    "token,expected",
    [
        ("(1,234.56)", "-1234.56"),
        ("123.45-", "-123.45"),
        ("-123.45", "-123.45"),
        ("45.00 DR", "-45.00"),
        ("45.00 CR", "45.00"),
        ("$ 1,234.56", "1234.56"),
        ("GBP 10.00", "10.00"),
        ("", None),
    ],
)
def test_money_patterns(token, expected):
    assert parse_money(token) == (Decimal(expected) if expected else None)


def test_european_and_suffix_meaning():
    assert parse_money("1.234,56", ",", ".") == Decimal("1234.56")
    assert parse_money("50 CR", suffix_negative="CR") == Decimal("-50.00")


@pytest.mark.parametrize(
    "token", ["NaN", "Infinity", "12,34", "1.234", "12oops", "--12", "(12", "12-34"]
)
def test_invalid_money_rejected(token):
    with pytest.raises(ValueError):
        parse_money(token)


@given(
    st.decimals(
        min_value="-9999999", max_value="9999999", places=2, allow_nan=False, allow_infinity=False
    )
)
def test_money_roundtrip(value):
    assert parse_money(format(value, ",.2f")) == value


@pytest.mark.parametrize(
    "token,order,expected",
    [
        ("31/01/2026", "DMY", date(2026, 1, 31)),
        ("01/31/2026", "MDY", date(2026, 1, 31)),
        ("2026-01-31", "YMD", date(2026, 1, 31)),
        ("31 Jan 2026", "auto", date(2026, 1, 31)),
        ("TUE 31-01-26", "DMY", date(2026, 1, 31)),
        ("Dec 31", "auto", date(2025, 12, 31)),
        ("01 Jan", "auto", date(2026, 1, 1)),
    ],
)
def test_dates_and_year_boundary(token, order, expected):
    parsed, flags = parse_date(token, order, date(2025, 12, 1), date(2026, 1, 31))
    assert parsed == expected
    assert flags == []


def test_date_ambiguity_unknown_year_and_outside_period():
    assert resolve_order(["01/02/2026", "05/06/2026"], "auto")[1] == ["DATE_ORDER_AMBIGUOUS"]
    assert resolve_order(["01/02/2026", "31/01/2026"], "auto")[0] == "DMY"
    assert parse_date("Jan 01", "auto", None, None)[1] == ["YEAR_UNKNOWN"]
    assert parse_date("2026-03-01", "YMD", date(2026, 1, 1), date(2026, 1, 31))[1] == [
        "DATE_OUT_OF_PERIOD"
    ]


def fixture(count=50, direction="asset"):
    balance = Decimal("1000")
    rows = []
    for i in range(count):
        balance += Decimal("-1") if direction == "asset" else Decimal("1")
        rows.append(
            RawRow(
                date=(date(2026, 1, 1) + timedelta(days=i)).isoformat(),
                description=f"Fake row {i}",
                debit="1.00",
                balance=str(balance),
                source_file="fake.pdf",
                raw_text="fake",
            )
        )
    summary = StatementSummary(
        opening=Decimal("1000"),
        closing=balance,
        total_debits=Decimal(count),
        total_credits=Decimal(0),
        direction=direction,
    )
    return rows, summary


@pytest.mark.parametrize("direction", ["asset", "liability"])
@pytest.mark.parametrize("wrong_index", list(range(50)))
def test_any_wrong_transaction_digit_is_flagged(direction, wrong_index):
    rows, summary = fixture(direction=direction)
    rows[wrong_index].debit = "9.00"
    statement = validate(normalize("test", rows, summary), Decimal("0.01"))
    assert statement.verdict == "NEEDS_REVIEW"
    assert [i for i, t in enumerate(statement.transactions) if t.check.status == "MISMATCH"] == [
        wrong_index
    ]


def test_reverse_order_and_totals_only():
    rows, summary = fixture(count=8)
    statement = validate(normalize("test", list(reversed(rows)), summary), Decimal("0.01"))
    assert statement.verdict == "VERIFIED"
    assert statement.transactions[0].date == date(2026, 1, 1)
    for row in rows:
        row.balance = ""
    statement = validate(normalize("test", rows, summary), Decimal("0.01"))
    assert statement.verdict == "VERIFIED_BY_TOTALS"


def test_missing_balance_and_unknown_amount_never_verify():
    rows, summary = fixture(count=3)
    rows[1].balance = ""
    statement = validate(normalize("test", rows, summary), Decimal("0.01"))
    assert statement.transactions[1].check.status == "UNVERIFIED"
    assert statement.verdict == "VERIFIED"
    rows[1].debit = "broken"
    statement = validate(normalize("test", rows, summary), Decimal("0.01"))
    assert statement.verdict == "NEEDS_REVIEW"
    assert "AMOUNT_UNPARSABLE" in statement.transactions[1].flags


def test_continuation_inherited_date_and_page_coverage():
    rows, summary = fixture(count=2)
    rows.insert(1, RawRow(description="wrapped detail", raw_text="original detail"))
    rows[-1].date = ""
    assembled = assemble(rows)
    assert assembled[0].description.endswith("wrapped detail")
    assert assembled[1].date_inherited
    statement = validate(normalize("test", rows, summary, pages=[1, 2]), Decimal("0.01"))
    assert "PAGE_COVERAGE" in statement.flags
    assert statement.verdict == "NEEDS_REVIEW"


def test_empty_and_ambiguous_statements_need_review():
    assert (
        validate(normalize("test", [], StatementSummary()), Decimal("0.01")).verdict
        == "NEEDS_REVIEW"
    )
    rows, summary = fixture(count=2)
    for row in rows:
        row.date = "01/02/2026"
    statement = validate(normalize("test", rows, summary), Decimal("0.01"))
    assert statement.verdict == "NEEDS_REVIEW"
    assert "DATE_ORDER_AMBIGUOUS" in statement.flags
