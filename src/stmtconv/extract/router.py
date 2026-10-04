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
    from stmtconv.errors import StmtconvError

    if mode not in {"auto", "text", "docling"}:
        raise StmtconvError("ENGINE_INVALID", "Choose auto, text or docling.")
    start = perf_counter()
    text = TextExtractor().extract(pages, profile)
    candidate = normalized(
        statement_id, text, pages, profile, date_order, tolerance, allowance_days
    )
    candidate.timings["text"] = perf_counter() - start
    reason = "text candidate"
    failed = candidate.verdict == "NEEDS_REVIEW"
    ratio = sum(t.check.status == "MISMATCH" for t in candidate.transactions) / max(
        len(candidate.transactions), 1
    )
    use_docling = mode == "docling" or (
        mode == "auto"
        and (pages.scanned or not candidate.transactions or failed or ratio > mismatch_ratio)
    )
    if use_docling:
        if docling is None:
            raise StmtconvError("DOCLING_MISSING", "OCR engine is not configured.")
        doc_start = perf_counter()
        try:
            result = docling.extract(pages, profile)
            other = normalized(
                statement_id, result, pages, profile, date_order, tolerance, allowance_days
            )
            other.timings["docling"] = perf_counter() - doc_start
            for row in other.transactions:
                if "SOURCE_CHECK_REQUIRED" not in row.flags:
                    row.flags.append("SOURCE_CHECK_REQUIRED")
            if mode == "docling" or score(other) < score(candidate):
                candidate = other
                reason = (
                    "scanned primary"
                    if pages.scanned
                    else "fallback improves whole-statement validation"
                )
            else:
                reason = "text retained; OCR candidate did not improve validation"
        except StmtconvError as exc:
            if mode == "docling":
                raise
            reason = "OCR fallback failed: " + exc.code
    if candidate.verdict == "NEEDS_REVIEW" and ai is not None:
        result = ai(candidate)
        other = normalized(
            statement_id, result, pages, profile, date_order, tolerance, allowance_days
        )
        if score(other) < score(candidate):
            candidate = other
            reason = "AI fallback improves whole-statement validation"
    for diagnostic in candidate.diagnostics.values():
        diagnostic["reason"] = reason
    candidate.timings["total"] = perf_counter() - start
    return candidate


def score(statement: Statement) -> tuple[int, int, int, int]:
    return (
        int(statement.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"}),
        sum(v is False for v in statement.checks.values()),
        sum(t.check.status == "MISMATCH" for t in statement.transactions),
        -len(statement.transactions),
    )
