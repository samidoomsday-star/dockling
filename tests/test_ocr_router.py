from decimal import Decimal
from pathlib import Path

import pytest

from stmtconv.config import load_settings
from stmtconv.demo import generate
from stmtconv.extract.base import ExtractionResult, PageSet
from stmtconv.extract.docling_engine import DoclingExtractor
from stmtconv.extract.router import route
from stmtconv.intake.service import analyze_pdf
from stmtconv.profiles.schema import load_profiles

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.slow
@pytest.mark.parametrize("layout", ["separate", "signed", "card"])
def test_scanned_real_ocr_rows_and_source_flags(layout, config_dir, tmp_path):
    load_settings(config_dir)
    path, truth = generate(tmp_path, layout=layout, count=5, scanned=True)
    profile = next(p for p in load_profiles(REPO / "profiles") if p.id == "synthetic_" + layout)
    extractor = DoclingExtractor(REPO / "models", 2)
    result = route(
        "ocr-test",
        PageSet(path, path.name, [1], True),
        profile,
        "YMD",
        Decimal("0.01"),
        7,
        "auto",
        extractor,
    )
    actual = [
        {
            "date": t.date.isoformat() if t.date else "",
            "description": t.description,
            "debit": str(t.debit or "0.00"),
            "credit": str(t.credit or "0.00"),
            "balance": str(t.balance) if t.balance is not None else "",
        }
        for t in result.transactions
    ]
    matched = sum(a == b for a, b in zip(actual, truth, strict=False))
    assert len(actual) == len(truth)
    assert matched / len(truth) >= 0.98
    assert all("SOURCE_CHECK_REQUIRED" in t.flags for t in result.transactions)
    assert all(t.engine == "docling" for t in result.transactions)
    assert result.timings["docling"] > 0
    assert result.diagnostics["1"]["engine"] == "docling"


def test_empty_fallback_cannot_replace_valid_text(config_dir, tmp_path):
    load_settings(config_dir)
    path, _ = generate(tmp_path, count=5)
    profile = next(p for p in load_profiles(REPO / "profiles") if p.id == "synthetic_separate")

    class Empty:
        def extract(self, pages, profile):
            from stmtconv.core.models import StatementSummary

            return ExtractionResult([], StatementSummary())

    result = route(
        "fake", PageSet(path, path.name, [1]), profile, "YMD", Decimal("0.01"), 7, "auto", Empty()
    )
    assert result.verdict == "VERIFIED"
    assert all(t.engine == "text" for t in result.transactions)


def test_borderless_text_is_supported_without_claiming_ocr_rescue(config_dir, tmp_path):
    load_settings(config_dir)
    path, truth = generate(tmp_path, count=9, borderless=True)
    profile = next(p for p in load_profiles(REPO / "profiles") if p.id == "synthetic_separate")
    result = route(
        "borderless", PageSet(path, path.name, [1, 2]), profile, "YMD", Decimal("0.01"), 7, "text"
    )
    assert len(result.transactions) == len(truth)
    assert result.verdict == "VERIFIED"
    assert len(analyze_pdf(path)) == 2
