import pytest
from typer.testing import CliRunner

from stmtconv import model_setup
from stmtconv.cli.app import app

runner = CliRunner()


def test_help_lists_inventory_without_workspace_or_model_import(tmp_path):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in [
        "doctor",
        "models",
        "order",
        "intake",
        "quote",
        "extract",
        "validate",
        "review",
        "apply-review",
        "spotcheck",
        "export",
        "deliver",
        "close",
        "profile",
        "run",
        "selftest",
        "stats",
    ]:
        assert command in result.output
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["deliver", "synthetic-id"],
    ],
)
def test_unknown_order_commands_are_safe_and_nonzero(args, config_dir, tmp_path):
    result = runner.invoke(app, ["--config-dir", str(config_dir), *args])
    assert result.exit_code == 1
    assert "ORDER_ID" in result.output
    assert not (tmp_path / "workspace/orders").exists()


def test_cli_invalid_setting_is_safe(config_dir, monkeypatch):
    monkeypatch.setenv("STMTCONV_NUM_THREADS", "private-test-value")
    result = runner.invoke(app, ["--config-dir", str(config_dir), "doctor"])
    assert result.exit_code == 1
    assert "CONFIG_INVALID" in result.output
    assert "private-test-value" not in result.output


def test_doctor_reports_missing_models_nonzero(config_dir):
    result = runner.invoke(app, ["--config-dir", str(config_dir), "doctor"])
    assert result.exit_code == 1
    assert "missing" in result.output
    assert "models download" in result.output


def test_doctor_does_not_display_api_key(config_dir, monkeypatch):
    monkeypatch.setenv("STMTCONV_AI_API_KEY", "synthetic-secret-key")
    result = runner.invoke(app, ["--config-dir", str(config_dir), "doctor"])
    assert "synthetic-secret-key" not in result.output


def test_models_command_calls_setup_service(config_dir, monkeypatch):
    seen = []

    def fake(settings):
        seen.append(settings.artifacts_path)
        return settings.artifacts_path

    monkeypatch.setattr(model_setup, "download", fake)
    result = runner.invoke(app, ["--config-dir", str(config_dir), "models", "download"])
    assert result.exit_code == 0
    assert len(seen) == 1
    assert "Models are ready" in result.output
