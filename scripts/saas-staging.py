"""Check an explicitly configured staging server or private field-validation record."""

import argparse
import json
from pathlib import Path

from stmtconv.config import load_hosted_settings
from stmtconv.web.field_validation import FieldRun, observations
from stmtconv.web.staging import preflight, private_file, report_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check", help="Read-only verified-TLS service checks; no deployment"
    )
    check.add_argument("--config", type=Path, default=Path(".staging-saas/server.env"))
    field = commands.add_parser("validate-field-run", help="Validate owner-recorded observations")
    field.add_argument("file", type=Path)
    args = parser.parse_args()
    path = args.config if args.command == "check" else args.file
    # Private configs/field records cannot be symlinks or group/world-readable.
    if not private_file(path):
        print(json.dumps({"status": "failed", "code": "PRIVATE_INPUT_REQUIRED"}))
        return 2
    try:
        if args.command == "check":
            extra = path.parent / "ai-key.env"
            if path.name == "server.env" and extra.exists() and not private_file(extra):
                raise ValueError("Private vault input required")
            report = preflight(load_hosted_settings(path))
            print(report_json(report))
            return 0 if report.status == "passed" else 2
        record = FieldRun.model_validate_json(path.read_bytes())
        print(json.dumps({"status": "valid_record", **observations(record)}, indent=2))
        return 0
    except Exception:
        # No file path, original data, URL, SQL or secret belongs in readiness output.
        print(json.dumps({"status": "failed", "code": "INVALID_PRIVATE_INPUT"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
