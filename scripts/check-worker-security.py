"""Verified Trivy worker-image scan. High/critical findings block the release gate."""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.75.0"
ARCHIVE = "trivy_0.75.0_Linux-64bit.tar.gz"
SHA256 = "c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f"


def scanner(local):
    directory = local / "tools/trivy"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle = directory / ARCHIVE
    if not bundle.exists():
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            with client.stream(
                "GET",
                f"https://github.com/aquasecurity/trivy/releases/download/v{VERSION}/{ARCHIVE}",
            ) as response:
                response.raise_for_status()
                count = 0
                with bundle.open("xb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        count += len(chunk)
                        if count > 200 * 1024**2:
                            raise ValueError("Scanner download exceeds bounds")
                        output.write(chunk)
    h = hashlib.sha256()
    with bundle.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != SHA256:
        raise ValueError("Official scanner artifact checksum failed; do not execute it")
    binary = directory / "trivy"
    with tarfile.open(bundle) as archive:
        member = archive.getmember("trivy")
        if not member.isfile() or member.size > 250 * 1024**2:
            raise ValueError("Invalid verified binary member")
        stream = archive.extractfile(member)
        with stream, binary.open("wb") as output:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                output.write(chunk)
    binary.chmod(0o700)
    return binary


def scan_coverage(report, image_id):
    metadata = report.get("Metadata", {})
    os_info = metadata.get("OS", {})
    family = os_info.get("Family")
    if (
        report.get("SchemaVersion") != 2
        or report.get("ArtifactType") != "container_image"
        or metadata.get("ImageID") != image_id
        or family not in {"debian", "ubuntu"}
        or not os_info.get("Name")
        or os_info.get("EOSL") is True
    ):
        raise ValueError("Image identity or supported OS scan evidence is unavailable")
    native = []
    python = []
    for result in report.get("Results", []):
        if result.get("Class") == "os-pkgs" and result.get("Type") == family:
            native.extend(result.get("Packages") or [])
        if result.get("Class") == "lang-pkgs" and result.get("Type") == "python-pkg":
            python.extend(result.get("Packages") or [])
    if not native or not {"docling", "torch", "opencv-python"}.issubset(
        {package.get("Name") for package in python}
    ):
        raise ValueError("Native and core Python package scan coverage is unavailable")
    return {
        "os": family,
        "os_version": os_info["Name"],
        "os_packages": len(native),
        "python_packages": len(python),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Record findings for development CI; never declares the release gate passed",
    )
    parser.add_argument(
        "--image",
        default="dockling-worker:phase2",
        help="Local worker image to scan; resolved to an immutable image ID",
    )
    args = parser.parse_args()
    selected = subprocess.run(
        ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    image_id = selected.stdout.strip()
    if selected.returncode != 0 or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise ValueError("Local worker image identity is unavailable")
    local = ROOT / ".local-saas"
    local.mkdir(mode=0o700, exist_ok=True)
    binary = scanner(local)
    output = local / "worker-security.json"
    log = local / "worker-security.log"
    with log.open("w") as private_log:
        result = subprocess.run(
            [
                str(binary),
                "image",
                "--image-src",
                "docker",
                "--scanners",
                "vuln",
                "--severity",
                "HIGH,CRITICAL",
                "--skip-java-db-update",
                "--list-all-pkgs",
                "--format",
                "json",
                "--output",
                str(output),
                "--cache-dir",
                str(local / "trivy-cache"),
                image_id,
            ],
            cwd=ROOT,
            stdout=private_log,
            stderr=private_log,
        )
    if result.returncode != 0:
        raise ValueError("Image scan unavailable; no clean-scan claim")
    report = json.loads(output.read_text())
    coverage = scan_coverage(report, image_id)
    findings = [v for r in report.get("Results", []) for v in r.get("Vulnerabilities", []) or []]
    high = sum(v["Severity"] == "HIGH" for v in findings)
    critical = sum(v["Severity"] == "CRITICAL" for v in findings)
    summary = {
        "scanner": "Trivy " + VERSION,
        "scanner_archive_sha256": SHA256,
        "image_id": report.get("Metadata", {}).get("ImageID"),
        "release_gate": "blocked" if findings else "passed",
        "high": high,
        "critical": critical,
        "unfixed": sum(not v.get("FixedVersion") for v in findings),
        "scope": "Final worker filesystem including native and vendored packages; independent review and other services remain separate.",
        "coverage": coverage,
    }
    (local / "worker-security-summary.json").write_text(json.dumps(summary, indent=2))
    output.chmod(0o600)
    log.chmod(0o600)
    print(json.dumps(summary, sort_keys=True))
    if findings and not args.report_only:
        raise SystemExit(1)
    if findings:
        print(
            "Development report recorded; the production release gate remains BLOCKED. No finding is suppressed."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "Worker security scan unavailable: "
            + type(error).__name__
            + ". Release remains blocked until verified."
        )
        raise SystemExit(2) from None
