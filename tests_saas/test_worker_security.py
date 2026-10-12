"""A missing or incomplete scan cannot certify a parser image for release."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

IMAGE = "sha256:" + "a" * 64


def runner(tmp_path, monkeypatch, report):
    spec = importlib.util.spec_from_file_location(
        "worker_security_test", "scripts/check-worker-security.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    monkeypatch.setattr(module, "scanner", lambda _local: Path("/fake/verified-trivy"))
    monkeypatch.setattr("sys.argv", ["check-worker-security.py"])

    def run(args, **_kwargs):
        if args[0] == "docker":
            return SimpleNamespace(returncode=0, stdout=IMAGE + "\n")
        (tmp_path / ".local-saas/worker-security.json").write_text(json.dumps(report))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", run)
    return module


def complete_report():
    return {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "Metadata": {"ImageID": IMAGE, "OS": {"Family": "ubuntu", "Name": "24.04"}},
        "Results": [
            {"Class": "os-pkgs", "Type": "ubuntu", "Packages": [{"Name": "libc6"}]},
            {
                "Class": "lang-pkgs",
                "Type": "python-pkg",
                "Packages": [{"Name": name} for name in ["docling", "torch", "opencv-python"]],
            },
        ],
    }


def test_empty_scan_cannot_clear_the_release_gate(tmp_path, monkeypatch):
    module = runner(tmp_path, monkeypatch, {"Metadata": {"ImageID": IMAGE}, "Results": []})
    with pytest.raises(ValueError):
        module.main()
    assert not (tmp_path / ".local-saas/worker-security-summary.json").exists()


@pytest.mark.parametrize("missing", ["os", "python", "image", "eol", "core_package"])
def test_incomplete_or_wrong_image_scan_is_unavailable(tmp_path, monkeypatch, missing):
    report = complete_report()
    if missing == "os":
        report["Results"] = report["Results"][1:]
    elif missing == "python":
        report["Results"] = report["Results"][:1]
    elif missing == "image":
        report["Metadata"]["ImageID"] = "sha256:" + "b" * 64
    elif missing == "eol":
        report["Metadata"]["OS"]["EOSL"] = True
    else:
        report["Results"][1]["Packages"] = [{"Name": "docling"}]
    module = runner(tmp_path, monkeypatch, report)
    with pytest.raises(ValueError):
        module.main()


def test_complete_scan_without_findings_passes(tmp_path, monkeypatch):
    module = runner(tmp_path, monkeypatch, complete_report())
    module.main()
    summary = json.loads((tmp_path / ".local-saas/worker-security-summary.json").read_text())
    assert summary["release_gate"] == "passed" and summary["image_id"] == IMAGE


def test_unfixed_critical_finding_still_blocks(tmp_path, monkeypatch):
    report = complete_report()
    report["Results"][0]["Vulnerabilities"] = [{"Severity": "CRITICAL"}]
    module = runner(tmp_path, monkeypatch, report)
    with pytest.raises(SystemExit) as stopped:
        module.main()
    assert stopped.value.code == 1
    summary = json.loads((tmp_path / ".local-saas/worker-security-summary.json").read_text())
    assert summary["critical"] == 1 and summary["unfixed"] == 1
