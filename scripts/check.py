"""Portable quality gate; commands use this interpreter and repository root."""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick", action="store_true", help="Skip format check and slow integration tests."
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commands = [["ruff", "check", "src", "tests", "scripts", "research/phase0", "tools/synth"]]
    if not args.quick:
        commands.append(
            [
                "ruff",
                "format",
                "--check",
                "src",
                "tests",
                "scripts",
                "research/phase0",
                "tools/synth",
            ]
        )
    commands += [["mypy"], ["pytest", *(["-m", "not slow"] if args.quick else [])]]
    for command in commands:
        print("Running:", " ".join(command), flush=True)
        result = subprocess.run([sys.executable, "-m", *command], cwd=root, check=False)
        if result.returncode:
            return result.returncode
    print("All requested development checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
