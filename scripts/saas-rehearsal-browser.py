"""Real HTTPS browser in its own test container, without changing host certificate trust."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rehearsal", ROOT / "scripts/saas-rehearsal.py")
assert spec and spec.loader
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)


def main() -> int:
    try:
        rehearsal.rehearsal_config()
        private = rehearsal.PRIVATE
        # This file is a disposable pointer to fresh fictional scopes, not matched secret material.
        path = private / "browser-workspaces.json"
        if path.is_symlink():
            raise ValueError("Private verification pointer cannot be a symlink")
        path.write_text(json.dumps(rehearsal.verification_workspaces()))
        path.chmod(0o600)
        environment = dict(os.environ)
        environment["DOCKER_CONFIG"] = str(ROOT / ".local-saas/docker")
        node_bin, certutil_bin = shutil.which("node"), shutil.which("certutil")
        if not node_bin or not certutil_bin:
            raise ValueError("Install Node 24 and libnss3-tools first")
        node, certutil = Path(node_bin).resolve(), Path(certutil_bin).resolve()
        libraries = Path("/usr/lib/x86_64-linux-gnu").resolve()
        browsers = Path(
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright"))
        ).resolve()
        if not libraries.is_dir() or not browsers.is_dir():
            raise ValueError("Install Linux x86 browser dependencies and Chromium first")
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--init",
                "--network",
                "host",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "512",
                "--memory",
                "2g",
                "--cpus",
                "2",
                "--tmpfs",
                "/tmp:rw,nosuid,size=512m",
                "--mount",
                f"type=bind,src={ROOT},dst={ROOT},readonly",
                "--mount",
                f"type=bind,src={private},dst={private}",
                "--mount",
                f"type=bind,src={node},dst={node},readonly",
                "--mount",
                f"type=bind,src={certutil},dst=/usr/bin/certutil,readonly",
                "--mount",
                f"type=bind,src={libraries},dst=/usr/lib/x86_64-linux-gnu,readonly",
                "--mount",
                f"type=bind,src={browsers},dst=/qa-browsers,readonly",
                "--mount",
                "type=bind,src=/usr/share/fonts,dst=/usr/share/fonts,readonly",
                "--mount",
                "type=bind,src=/usr/share/fontconfig,dst=/usr/share/fontconfig,readonly",
                "--mount",
                "type=bind,src=/etc/fonts,dst=/etc/fonts,readonly",
                "--env",
                f"NODE_EXTRA_CA_CERTS={private / 'tls/ca.pem'}",
                "--env",
                "PLAYWRIGHT_BROWSERS_PATH=/qa-browsers",
                "--workdir",
                str(ROOT),
                "python@sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b",
                str(node),
                "scripts/saas-rehearsal-browser.mjs",
                "--provisioned-workspaces",
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "code": "HTTPS_BROWSER_CHECK_REQUIRED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
