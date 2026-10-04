import os
from decimal import Decimal

import pytest

from stmtconv.catalog import load_catalog
from stmtconv.config import load_settings, model_download_environment
from stmtconv.errors import ConfigurationError


def test_environment_then_dotenv_then_yaml(config_dir, monkeypatch, tmp_path):
    env = tmp_path / "personal.env"
    env.write_text(
        "STMTCONV_NUM_THREADS=2\nSTMTCONV_WORKSPACE=space name/বাংলা\nSTMTCONV_AI_API_KEY=synthetic-private-key\n"
    )
    monkeypatch.setenv("STMTCONV_NUM_THREADS", "3")
    settings = load_settings(config_dir, env)
    assert settings.num_threads == 3
    assert settings.workspace == (tmp_path / "space name/বাংলা").resolve()
    assert settings.balance_tolerance == Decimal("0.01")
    assert "synthetic-private-key" not in repr(settings)
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_dotenv_artifacts_alias(config_dir, tmp_path):
    env = tmp_path / "personal.env"
    env.write_text("DOCLING_ARTIFACTS_PATH=custom models\n")
    assert load_settings(config_dir, env).artifacts_path == tmp_path / "custom models"


def test_invalid_setting_hides_input(config_dir, monkeypatch):
    monkeypatch.setenv("STMTCONV_NUM_THREADS", "synthetic-secret-must-not-print")
    with pytest.raises(ConfigurationError) as caught:
        load_settings(config_dir)
    assert "num_threads" in caught.value.message
    assert "synthetic-secret-must-not-print" not in str(caught.value)


@pytest.mark.parametrize(
    "content", ["- a list", "workspace: [broken", "num_threads: 0", "balance_tolerance: 0.01"]
)
def test_bad_settings_stop_configuration(config_dir, content):
    (config_dir / "settings.yaml").write_text(content)
    with pytest.raises(ConfigurationError):
        load_settings(config_dir)


def test_bad_catalog_reports_filename_and_field(config_dir):
    (config_dir / "pricing.yaml").write_text("packages: []\naddons: {}\n")
    with pytest.raises(ConfigurationError) as caught:
        load_catalog(config_dir)
    assert "pricing.yaml" in caught.value.message
    assert "packages" in caught.value.message


def test_bundled_defaults_work_outside_checkout(tmp_path):
    settings = load_settings()
    assert settings.workspace == tmp_path / "workspace"


def test_setup_network_exception_restores_flags_on_failure():
    with pytest.raises(RuntimeError), model_download_environment():
        assert os.environ["HF_HUB_OFFLINE"] == "0"
        raise RuntimeError("fake download failure")
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_setup_cache_is_writable_and_restored_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", "original-cache")
    with pytest.raises(RuntimeError), model_download_environment(tmp_path / "cache"):
        target = tmp_path / "cache" / "hub"
        assert os.environ["HF_HUB_CACHE"] == str(target)
        (target / "probe").write_text("synthetic")
        raise RuntimeError("fake download failure")
    assert os.environ["HF_HUB_CACHE"] == "original-cache"
