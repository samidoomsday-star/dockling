import hashlib
import os

import pytest

from stmtconv import model_setup
from stmtconv.config import load_settings
from stmtconv.errors import SetupError


def manifest(content=b"synthetic artifact", path="weights.bin"):
    return model_setup.Manifest(
        note="synthetic fixture",
        files=[
            model_setup.Artifact(
                path=path, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()
            )
        ],
        huggingface_commit_metadata={},
    )


def test_tampered_artifacts_fail_without_changing_expected_hash(tmp_path):
    expected = manifest()
    original = expected.files[0].sha256
    (tmp_path / "weights.bin").write_bytes(b"wrong bytes")
    with pytest.raises(SetupError, match="differs"):
        model_setup.verify_artifacts(tmp_path, expected)
    assert expected.files[0].sha256 == original


def test_manifest_cannot_escape_model_directory(tmp_path):
    with pytest.raises(SetupError, match="escapes"):
        model_setup.missing_artifacts(tmp_path, manifest(path="../other/weights.bin"))


def test_download_exception_never_exposes_provider_error(config_dir, monkeypatch):
    monkeypatch.setattr(model_setup, "load_manifest", manifest)

    def broken(**kwargs):
        assert os.environ["HF_HUB_OFFLINE"] == "0"
        raise RuntimeError("secret-token-and-signed-url-must-not-print")

    with pytest.raises(SetupError) as caught:
        model_setup.download(load_settings(config_dir), broken)
    assert "secret-token" not in str(caught.value)
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_download_verifies_bytes_and_restores_offline(config_dir, monkeypatch):
    monkeypatch.setattr(model_setup, "load_manifest", manifest)

    def fake(**kwargs):
        path = kwargs["output_dir"]
        path.mkdir(parents=True, exist_ok=True)
        (path / "weights.bin").write_bytes(b"synthetic artifact")
        return path

    settings = load_settings(config_dir)
    assert model_setup.download(settings, fake) == settings.artifacts_path
    assert os.environ["HF_HUB_OFFLINE"] == "1"
