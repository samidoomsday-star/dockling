from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from stmtconv.catalog import load_catalog
from stmtconv.config import load_settings
from stmtconv.demo import generate
from stmtconv.errors import StmtconvError
from stmtconv.export.delivery import deliver
from stmtconv.export.service import export
from stmtconv.extract.service import extract, persist, read_statements
from stmtconv.intake.service import intake
from stmtconv.orders import ledger, store
from stmtconv.pipeline import run
from stmtconv.privacy import deletion
from stmtconv.review.service import record_spotcheck


def setup(config_dir):
    settings = load_settings(config_dir)
    order = store.create(settings.workspace, alias="PRIVATE_SYNTHETIC_CLIENT")
    folder = store.root(settings.workspace, order.order_id) / "input"
    path, _ = generate(folder, count=5)
    path.with_suffix(".json").unlink()
    intake(settings, order.order_id)
    extract(settings, order.order_id, engine="text")
    record_spotcheck(settings, order.order_id, True, "source checked")
    export(settings, order.order_id, load_catalog(config_dir).exports)
    return settings, order.order_id


def test_delivery_matches_summary_and_close_scrubs_everything(config_dir):
    settings, order_id = setup(config_dir)
    root = store.root(settings.workspace, order_id)
    output = next((root / "output").glob("*.xlsx"))
    summary = dict(load_workbook(output)["Summary"].values)
    archive = deliver(settings, order_id)
    with ZipFile(archive) as zipped:
        note = zipped.read("DELIVERY-NOTE.txt").decode()
        assert f"Transactions: {summary['rows']}" in note
        assert f"Manual fixes: {summary['fixes']}" in note
        assert "Spot-check skipped: False" in note
    descriptions = [row.description for row in read_statements(settings, order_id)[0].transactions]
    certificate = deletion.close(settings, order_id)
    assert certificate["files"]
    assert sorted(p.name for p in root.rglob("*")) == ["order.json"]
    text = (root / "order.json").read_text()
    metrics = (settings.workspace / "ledger.jsonl").read_text()
    for private in [
        "PRIVATE_SYNTHETIC_CLIENT",
        *descriptions,
        "separate-2026-01-text.pdf",
        "1000.00",
    ]:
        assert private not in text + metrics
    assert store.load(settings.workspace, order_id).status == "closed"
    assert ledger.stats(settings.workspace)["orders"] == 1
    assert ledger.stats(settings.workspace)["median_seconds_per_page"]["text"] > 0
    # Retry is safe and does not duplicate the anonymous ledger.
    assert deletion.close(settings, order_id) == certificate
    assert len(ledger.read(settings.workspace)) == 1


def test_changed_output_is_refused(config_dir):
    settings, order_id = setup(config_dir)
    path = next((store.root(settings.workspace, order_id) / "output").glob("*.csv"))
    path.write_bytes(b"tampered")
    with pytest.raises(StmtconvError, match="changed"):
        deliver(settings, order_id)
    assert store.load(settings.workspace, order_id).status == "exported"


def test_spotcheck_is_invalidated_by_changed_data(config_dir):
    settings = load_settings(config_dir)
    order = store.create(settings.workspace)
    folder = store.root(settings.workspace, order.order_id) / "input"
    path, _ = generate(folder, count=5)
    path.with_suffix(".json").unlink()
    intake(settings, order.order_id)
    extract(settings, order.order_id, engine="text")
    record_spotcheck(settings, order.order_id, True)
    statements = read_statements(settings, order.order_id)
    statements[0].transactions[0].description = "changed description"
    persist(settings, order.order_id, statements)
    with pytest.raises(StmtconvError, match="changed after"):
        export(settings, order.order_id, load_catalog(config_dir).exports)


def test_partial_deletion_is_not_certified_and_retry_finishes(config_dir, monkeypatch):
    settings, order_id = setup(config_dir)
    deliver(settings, order_id)
    real = deletion.shutil.rmtree

    def fail_work(path, *args, **kwargs):
        if Path(path).name == "work":
            raise PermissionError("synthetic locked file")
        return real(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(deletion.shutil, "rmtree", fail_work)
        with pytest.raises(StmtconvError, match="no success certificate"):
            deletion.close(settings, order_id)
    order = store.load(settings.workspace, order_id)
    assert order.deletion_pending and order.deletion_certificate is None
    assert order.status == "delivered" and order.error_code == "DELETION_PARTIAL"
    deletion.close(settings, order_id)
    assert store.load(settings.workspace, order_id).status == "closed"


def test_symlink_deletion_refused_without_touching_target(config_dir, tmp_path):
    settings, order_id = setup(config_dir)
    deliver(settings, order_id)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "keep.txt"
    target.write_text("keep")
    (store.root(settings.workspace, order_id) / "work/link").symlink_to(
        outside, target_is_directory=True
    )
    with pytest.raises(StmtconvError, match="symbolic link"):
        deletion.close(settings, order_id)
    assert target.read_text() == "keep"


def test_pipeline_pauses_for_spotcheck_then_delivers(config_dir):
    settings = load_settings(config_dir)
    catalog = load_catalog(config_dir)
    order = store.create(settings.workspace)
    folder = store.root(settings.workspace, order.order_id) / "input"
    path, _ = generate(folder, count=5)
    path.with_suffix(".json").unlink()
    message, paths = run(settings, catalog, order.order_id)
    assert message == "Run spotcheck, then run again" and paths == []
    record_spotcheck(settings, order.order_id, True)
    message, paths = run(settings, catalog, order.order_id)
    assert message == "Delivered" and paths[0].is_file()
