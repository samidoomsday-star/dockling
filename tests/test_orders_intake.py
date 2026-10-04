from decimal import Decimal

import pytest

from stmtconv.catalog import load_catalog
from stmtconv.config import load_settings
from stmtconv.demo import generate
from stmtconv.errors import OrderStateError, StmtconvError
from stmtconv.intake.quote import quote
from stmtconv.intake.service import intake, sniff
from stmtconv.orders import store
from stmtconv.orders.models import TRANSITIONS, Status


@pytest.mark.parametrize("source", list(TRANSITIONS))
@pytest.mark.parametrize("target", list(TRANSITIONS))
def test_every_transition(source: Status, target: Status, tmp_path):
    order = store.create(tmp_path)
    order.status = source
    if target in TRANSITIONS[source]:
        store.transition(order, target, "TEST_ERROR" if target == "failed" else None)
        assert order.status == target
        assert order.status_history[-1].status == target
    else:
        with pytest.raises(OrderStateError):
            store.transition(order, target, "TEST_ERROR")
        assert order.status == source


def test_manifest_is_atomic_on_failure_and_locked(tmp_path):
    order = store.create(tmp_path, alias="fake alias")
    with pytest.raises(RuntimeError), store.edit(tmp_path, order.order_id) as edited:
        edited.client_alias = "changed"
        with pytest.raises(StmtconvError, match="Another command"):
            with store.edit(tmp_path, order.order_id):
                pass
        raise RuntimeError("abort")
    assert store.load(tmp_path, order.order_id).client_alias == "fake alias"
    assert not (store.root(tmp_path, order.order_id) / ".lock").exists()


def test_path_escape_and_symlink_are_rejected(tmp_path):
    with pytest.raises(StmtconvError):
        store.root(tmp_path, "../escape")
    order = store.create(tmp_path)
    root = store.root(tmp_path, order.order_id)
    with pytest.raises(StmtconvError):
        store.child(root, "../outside")
    (root / "work/link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(StmtconvError):
        store.child(root, "work/link/file")


@pytest.mark.parametrize("layout", ["separate", "signed", "card"])
def test_synthetic_intake_text_and_scan(layout, config_dir, tmp_path):
    settings = load_settings(config_dir)
    for scanned in [False, True]:
        order = store.create(settings.workspace)
        input_dir = store.root(settings.workspace, order.order_id) / "input"
        generate(input_dir, layout=layout, count=9, rows_per_page=5, scanned=scanned)
        # Ground truth is not a client input format.
        for path in input_dir.glob("*.json"):
            path.unlink()
        facts = intake(settings, order.order_id)
        assert len(facts[0].pages) == 2
        assert all(p.kind == ("scanned" if scanned else "text") for p in facts[0].pages)
        assert store.load(settings.workspace, order.order_id).status == "intake_done"


def test_password_is_never_persisted(config_dir):
    settings = load_settings(config_dir)
    order = store.create(settings.workspace)
    root = store.root(settings.workspace, order.order_id)
    generate(root / "input", count=3, password="SyntheticPassword42")
    for p in (root / "input").glob("*.json"):
        p.unlink()
    with pytest.raises(StmtconvError, match="password"):
        intake(settings, order.order_id)
    facts = intake(settings, order.order_id, password="SyntheticPassword42")
    assert facts[0].password_protected
    for path in root.rglob("*"):
        if path.is_file():
            assert b"SyntheticPassword42" not in path.read_bytes()


def test_twelve_scanned_pages_quote_standard_with_surcharge(config_dir):
    settings = load_settings(config_dir)
    order = store.create(settings.workspace)
    order.pages_by_kind = {"scanned": 12}
    result = quote(order, load_catalog(config_dir).pricing, settings)
    assert result.package == "standard"
    assert (result.price_min, result.price_max) == (Decimal("37.50"), Decimal("50.00"))
    assert result.addons == ["scanned"]


def test_content_sniff_rejects_misleading_extension(tmp_path):
    file = tmp_path / "invoice.pdf"
    file.write_text("not a PDF")
    with pytest.raises(StmtconvError):
        sniff(file)
