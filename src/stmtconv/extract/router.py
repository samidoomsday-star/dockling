"""Statement-wide candidates preserve sequence and undergo the same validation."""

from collections.abc import Callable
from decimal import Decimal
from time import perf_counter

from stmtconv.core.models import Statement
from stmtconv.core.normalize import normalize
from stmtconv.core.validate import validate
from stmtconv.extract.base import ExtractionResult, Extractor, PageSet
from stmtconv.extract.text_engine import TextExtractor
from stmtconv.profiles.schema import Profile


def normalized(
    statement_id: str,
    result: ExtractionResult,
    pages: PageSet,
    profile: Profile,
    date_order: str,
    tolerance: Decimal,
    allowance_days: int,
) -> Statement:
    from typing import cast

    from stmtconv.core.dates import DateOrder

    chosen = profile.date_order if date_order == "auto" else cast(DateOrder, date_order)
    statement = normalize(
        statement_id,
        result.rows,
        result.summary,
        chosen,
        profile.decimal_separator,
        profile.thousands_separator,
        profile.amount_style,
        profile.date_formats,
        allowance_days,
        pages.pages,
    )
    statement.flags.extend(result.flags)
    statement.summary_pages = result.summary_pages
    statement.diagnostics = result.diagnostics
    return validate(statement, tolerance, profile.row_order)


def route(
    statement_id: str,
    pages: PageSet,
    profile: Profile,
    date_order: str,
    tolerance: Decimal,
    allowance_days: int,
    mode: str = "text",
    docling: Extractor | None = None,
    ai: Callable[[Statement], ExtractionResult] | None = None,
    mismatch_ratio: float = 0.05,
) -> Statement:
    start = perf_counter()
    text = TextExtractor().extract(pages, profile)
    candidate = normalized(
        statement_id, text, pages, profile, date_order, tolerance, allowance_days
    )
    candidate.timings["text"] = perf_counter() - start
    return candidate
