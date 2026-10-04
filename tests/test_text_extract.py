from pathlib import Path

import pytest

from stmtconv.config import load_settings
from stmtconv.demo import generate
from stmtconv.errors import StmtconvError
from stmtconv.extract.service import extract, page_groups
from stmtconv.intake.service import intake
from stmtconv.orders import store
from stmtconv.profiles.schema import detect, load_profiles
from stmtconv.selftest import run

REPO = Path(__file__).resolve().parents[1]


def test_nine_layout_ground_truth_cases(config_dir):
    result = run(load_settings(config_dir))
    assert result["passed"]
    assert len(result["results"]) == 9
    assert all(r["matched"] for r in result["results"])


def test_changed_pdf_digit_is_flagged(config_dir):
    settings = load_settings(config_dir)
    order = store.create(settings.workspace)
    folder = store.root(settings.workspace, order.order_id) / "input"
    file, _ = generate(folder, count=12, corrupt_index=1)
    file.with_suffix(".json").unlink()
    intake(settings, order.order_id)
    statement = extract(settings, order.order_id)[0]
    assert statement.verdict == "NEEDS_REVIEW"
    assert sum(t.check.status == "MISMATCH" for t in statement.transactions) == 1
    assert store.load(settings.workspace, order.order_id).status == "needs_review"


def test_layout_fingerprints_stay_out_of_processing_code():
    profiles = load_profiles(REPO / "profiles")
    for file in (REPO / "src").rglob("*.py"):
        content = file.read_text()
        assert all(
            fingerprint not in content
            for profile in profiles
            for fingerprint in profile.fingerprints
        )
    assert detect("unknown layout", profiles).id == "generic"
    with pytest.raises(StmtconvError):
        detect("", profiles, "missing")


def test_page_groups_reject_overlap_and_outside():
    assert page_groups("1-4,5-9", 9) == [list(range(1, 5)), list(range(5, 10))]
    for invalid in ["0", "1-99", "1-3,2-4", "abc", "4-1"]:
        with pytest.raises(StmtconvError):
            page_groups(invalid, 9)
