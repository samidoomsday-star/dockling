"""Typed anonymous metrics; appends are exclusive and idempotent by order ID."""

from collections import Counter
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from stmtconv.errors import StmtconvError
from stmtconv.orders import store


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["delivered", "abandoned"] = "delivered"
    order_id: str
    platform: str
    package: str
    pages_by_kind: dict[str, int]
    statements: int
    engines: dict[str, int]
    seconds_per_stage: dict[str, float]
    seconds_per_page: dict[str, float]
    verdicts: dict[str, int]
    manual_fixes: int
    review_minutes: float
    ai_pages_used: int = 0


def read(workspace: Path) -> list[Metrics]:
    path = workspace / "ledger.jsonl"
    if path.is_symlink():
        raise StmtconvError("LEDGER_PATH", "Ledger must remain inside the workspace.")
    if not path.exists():
        return []
    try:
        return [
            Metrics.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, ValidationError) as exc:
        raise StmtconvError("LEDGER_READ", "The anonymous metrics ledger is invalid.") from exc


def append(workspace: Path, metrics: Metrics) -> None:
    path = workspace / "ledger.jsonl"
    lock = workspace / ".ledger.lock"
    if lock.is_symlink():
        raise StmtconvError("LEDGER_PATH", "Ledger lock cannot be a symbolic link.")
    try:
        stream = lock.open("x")
    except FileExistsError as exc:
        raise StmtconvError(
            "LEDGER_BUSY",
            "Another command is updating metrics.",
            "Retry once that command finishes.",
        ) from exc
    try:
        with stream:
            rows = read(workspace)
            if any(row.order_id == metrics.order_id for row in rows):
                return
            # Atomic rewrite prevents a half-written last JSON line on interruption.
            store.atomic_text(
                path, "".join(row.model_dump_json() + "\n" for row in [*rows, metrics])
            )
    finally:
        lock.unlink(missing_ok=True)


def stats(workspace: Path) -> dict[str, object]:
    rows = read(workspace)
    return {
        "orders": len(rows),
        "pages": dict(sum((Counter(row.pages_by_kind) for row in rows), Counter())),
        "median_seconds_per_page": {
            kind: median(values)
            for kind in ["text", "scanned"]
            if (
                values := [
                    row.seconds_per_page[kind] for row in rows if kind in row.seconds_per_page
                ]
            )
        },
        "verdicts": dict(sum((Counter(row.verdicts) for row in rows), Counter())),
    }
