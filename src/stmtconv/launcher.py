"""Move an operator's drop-folder files into a new tracked order, then run it."""

import shutil
from pathlib import Path

from stmtconv.catalog import Catalog
from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.intake.service import sniff
from stmtconv.orders import store
from stmtconv.pipeline import run


def launch(settings: Settings, catalog: Catalog, inbox: Path) -> tuple[str, str, list[Path]]:
    if not inbox.exists():
        inbox.mkdir(parents=True)
    if inbox.is_symlink():
        raise StmtconvError("INBOX_PATH", "Inbox cannot be a symbolic link.")
    paths = sorted(inbox.iterdir())
    if not paths:
        raise StmtconvError("INBOX_EMPTY", "Drop PDF or image statements into inbox first.")
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise StmtconvError("INBOX_PATH", "Inbox must contain regular files only.")
    for path in paths:
        sniff(path)
    order = store.create(settings.workspace)
    folder = store.root(settings.workspace, order.order_id) / "input"
    transferred = []
    try:
        for path in paths:
            destination = folder / path.name
            shutil.move(str(path), destination)
            transferred.append((path, destination))
    except OSError as exc:
        for source, destination in reversed(transferred):
            if not source.exists():
                shutil.move(str(destination), source)
        raise StmtconvError(
            "INBOX_MOVE",
            f"Could not transfer all files. Order ID: {order.order_id}.",
            "Files remain in inbox or that order input folder; inspect before retrying.",
        ) from exc
    try:
        message, outputs = run(settings, catalog, order.order_id)
    except StmtconvError as exc:
        raise StmtconvError(
            exc.code,
            exc.message,
            f"Order ID: {order.order_id}. Inspect its input folder before retrying.",
        ) from exc
    return order.order_id, message, outputs
