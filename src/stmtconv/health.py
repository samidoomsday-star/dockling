"""Local setup diagnostics; no Docling import, client reads or network requests."""

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from stmtconv.config import Settings
from stmtconv.errors import SetupError
from stmtconv.model_setup import load_manifest, missing_artifacts


@dataclass(frozen=True)
class Check:
    name: str
    status: Literal["PASS", "WARN", "FAIL"]
    detail: str


def prepare_workspace(workspace: Path) -> None:
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=workspace) as probe:
            probe.write(b"setup check")
    except OSError as exc:
        raise SetupError(
            "WORKSPACE_WRITE",
            "The workspace is not writable.",
            "Choose another STMTCONV_WORKSPACE folder.",
        ) from exc


def inspect(settings: Settings) -> list[Check]:
    checks = [
        Check(
            "Python", "PASS" if sys.version_info[:2] == (3, 12) else "FAIL", sys.version.split()[0]
        ),
        Check(
            "Virtual environment",
            "PASS" if sys.prefix != sys.base_prefix else "WARN",
            "Active" if sys.prefix != sys.base_prefix else "Use a Python 3.12 virtual environment.",
        ),
        Check("Workspace", "PASS", str(settings.workspace)),
        Check(
            "Offline processing",
            "PASS" if settings.offline else "WARN",
            "Enabled" if settings.offline else "Disabled in settings; enable for local processing.",
        ),
    ]
    try:
        prepare_workspace(settings.workspace)
        free = shutil.disk_usage(settings.workspace).free / 1024**3
        checks.append(
            Check(
                "Free disk",
                "PASS" if free >= 5 else "WARN",
                f"{free:.1f} GiB available (5 GiB recommended).",
            )
        )
    except SetupError:
        checks.append(Check("Workspace writable", "FAIL", "Choose a writable workspace folder."))
    missing = missing_artifacts(settings.artifacts_path, load_manifest())
    checks.append(
        Check(
            "Models",
            "FAIL" if missing else "PASS",
            f"{len(missing)} files missing; run models download."
            if missing
            else "Pinned artifact files present (presence check; download verifies hashes).",
        )
    )
    if any(
        "onedrive" in part.lower() or "dropbox" in part.lower() for part in settings.workspace.parts
    ):
        checks.append(
            Check(
                "Cloud sync",
                "WARN",
                "Move the workspace outside OneDrive/Dropbox before client work.",
            )
        )
    checks.append(
        Check(
            "Disk encryption",
            "WARN",
            "Confirm BitLocker/device encryption on your Windows device; not verified here.",
        )
    )
    checks.append(
        Check(
            "AI key",
            "PASS",
            "Environment key present (hidden); optional AI requires consent and explicit activation."
            if settings.ai_api_key
            else "No environment key; local conversion needs none. Optional BYOK uses ai setup.",
        )
    )
    return checks
