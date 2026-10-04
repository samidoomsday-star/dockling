import pytest

from stmtconv import health
from stmtconv.config import load_settings
from stmtconv.errors import SetupError


def test_doctor_flags_missing_models_and_sync_folder(config_dir, monkeypatch, tmp_path):
    monkeypatch.setenv("STMTCONV_WORKSPACE", str(tmp_path / "OneDrive - Synthetic/work"))
    checks = health.inspect(load_settings(config_dir))
    assert any(c.name == "Models" and c.status == "FAIL" for c in checks)
    assert any(c.name == "Cloud sync" and c.status == "WARN" for c in checks)
    assert any(c.name == "Disk encryption" and c.status == "WARN" for c in checks)


def test_workspace_file_is_rejected_without_overwrite(tmp_path):
    path = tmp_path / "existing-file"
    path.write_text("preserve me")
    with pytest.raises(SetupError):
        health.prepare_workspace(path)
    assert path.read_text() == "preserve me"


def test_probe_leaves_no_files_in_new_workspace(tmp_path):
    path = tmp_path / "space/বাংলা"
    health.prepare_workspace(path)
    assert list(path.iterdir()) == []
