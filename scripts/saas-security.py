"""Reproducible public dependency/license inventory and explicit package advisory checks.

Only package names/versions are sent to OSV/npm. No document/config/key is inspected.
"""

import argparse
import importlib.metadata
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    python = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name or name == "stmtconv":
            continue
        python.append(
            {
                "name": name,
                "version": distribution.version,
                "license": distribution.metadata.get("License-Expression")
                or distribution.metadata.get("License")
                or "requires review",
            }
        )
    python.sort(key=lambda p: p["name"].lower())
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    node = []
    for name, entry in lock["packages"].items():
        if "node_modules/" in name:
            node.append(
                {
                    "name": name.rsplit("node_modules/", 1)[1],
                    "version": entry["version"],
                    "license": entry.get("license", "requires review"),
                    "development": entry.get("dev", False),
                }
            )
    return {
        "format": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "python": python,
        "node": node,
        "models": {
            "manifest": "docs/PHASE0-MODEL-MANIFEST.json",
            "terms_review": "docs/saas/PHASE6-OPERATIONS.md",
        },
        "scope": "Installed Python environment and locked frontend; native image/provider/security review is separate.",
    }


def audit(report):
    findings = []
    with httpx.Client(timeout=20) as client:
        packages = report["python"]
        for offset in range(0, len(packages), 100):
            batch = packages[offset : offset + 100]
            response = client.post(
                "https://api.osv.dev/v1/querybatch",
                json={
                    "queries": [
                        {
                            "package": {"name": p["name"], "ecosystem": "PyPI"},
                            "version": p["version"],
                        }
                        for p in batch
                    ]
                },
            )
            response.raise_for_status()
            results = response.json()["results"]
            if len(results) != len(batch):
                raise ValueError("Incomplete advisory check")
            for package, result in zip(batch, results, strict=True):
                if result.get("vulns"):
                    findings.append(
                        {
                            "name": package["name"],
                            "version": package["version"],
                            "advisories": sorted(v["id"] for v in result["vulns"]),
                        }
                    )
    npm = subprocess.run(
        ["npm", "audit", "--json", "--prefix", str(ROOT / "frontend")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    result = json.loads(npm.stdout)
    if result.get("error") or "metadata" not in result:
        raise ValueError("Npm advisory service unavailable")
    counts = result["metadata"]["vulnerabilities"]
    report["audit"] = {
        "status": "checked",
        "python_service": "OSV",
        "python_packages": len(packages),
        "python_findings": findings,
        "node_service": "npm audit",
        "node_counts": counts,
        "coverage": "No known advisories returned is not an independent security signoff or native-image scan.",
    }
    return bool(findings or counts["total"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Explicit network check of public package names/versions",
    )
    args = parser.parse_args()
    report = inventory()
    failed = audit(report) if args.audit else False
    local = ROOT / ".local-saas"
    local.mkdir(exist_ok=True, mode=0o700)
    output = local / "security-inventory.json"
    output.write_text(json.dumps(report, indent=2))
    output.chmod(0o600)
    print(
        f"Inventory: {len(report['python'])} Python packages; {len(report['node'])} frontend package records."
    )
    if args.audit:
        print(
            "Advisory checks: "
            + ("findings require review" if failed else "no known package advisories returned")
            + "; native image and independent review remain separate."
        )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "Dependency check unavailable: "
            + type(error).__name__
            + ". No clean-scan claim is made."
        )
        raise SystemExit(2) from None
