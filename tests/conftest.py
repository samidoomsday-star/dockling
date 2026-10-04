import logging
import os
import shutil
import socket
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolate_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for name in list(os.environ):
        if name.startswith("STMTCONV_") or name in {
            "DOCLING_ARTIFACTS_PATH",
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
        }:
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    def no_network(*args, **kwargs):
        raise AssertionError("Automated tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in previous_handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(previous_level)


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(REPO / "config", target)
    return target
