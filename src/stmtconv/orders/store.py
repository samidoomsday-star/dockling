"""Confined order paths, exclusive mutations and atomic durable manifests."""

import json
import re
import secrets
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from stmtconv.errors import OrderStateError, StmtconvError
from stmtconv.orders.models import TRANSITIONS, Event, Order, Status


def atomic_text(path: Path, content: str) -> None:
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def root(workspace: Path, order_id: str) -> Path:
    if not re.fullmatch(r"\d{8}-(fiverr|upwork|direct|test)-[a-z0-9]{8}", order_id):
        raise StmtconvError("ORDER_ID", "Invalid order ID.")
    orders = workspace / "orders"
    target = orders / order_id
    if (
        orders.is_symlink()
        or target.is_symlink()
        or not target.resolve().is_relative_to(workspace.resolve())
    ):
        raise StmtconvError("ORDER_PATH", "Order folder must remain inside its workspace.")
    return target


def child(order_root: Path, relative: str) -> Path:
    path = order_root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(order_root.resolve()):
        raise StmtconvError("ORDER_PATH", "An order path escapes its folder.")
    for part in [path, *path.parents]:
        if part == order_root.parent:
            break
        if part.is_symlink():
            raise StmtconvError("ORDER_PATH", "Symbolic links are not allowed in order folders.")
    return path


def load(workspace: Path, order_id: str) -> Order:
    path = child(root(workspace, order_id), "order.json")
    try:
        order = Order.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise StmtconvError("ORDER_READ", "Order is missing or its manifest is invalid.") from exc
    if order.order_id != order_id:
        raise StmtconvError("ORDER_ID", "Manifest ID does not match its folder.")
    return order


def save(workspace: Path, order: Order) -> None:
    validated = Order.model_validate(order.model_dump())
    atomic_text(
        child(root(workspace, order.order_id), "order.json"),
        validated.model_dump_json(indent=2) + "\n",
    )


@contextmanager
def edit(workspace: Path, order_id: str) -> Iterator[Order]:
    lock = child(root(workspace, order_id), ".lock")
    try:
        stream = lock.open("x")
    except FileExistsError as exc:
        raise StmtconvError(
            "ORDER_BUSY",
            "Another command is editing this order.",
            "If a command crashed, check it has stopped before removing its .lock file.",
        ) from exc
    try:
        with stream:
            order = load(workspace, order_id)
            yield order
            save(workspace, order)
    finally:
        lock.unlink(missing_ok=True)


def transition(order: Order, status: Status, error_code: str | None = None) -> None:
    if status not in TRANSITIONS[order.status]:
        raise OrderStateError("ORDER_STATE", f"Cannot move from {order.status} to {status}.")
    if status == "failed" and not error_code:
        raise OrderStateError("ORDER_STATE", "A failed order requires an error code.")
    order.status = status
    order.error_code = error_code
    order.status_history.append(Event(status=status, at=datetime.now(UTC)))


def require(order: Order, allowed: set[Status]) -> None:
    if order.status not in allowed:
        raise OrderStateError(
            "ORDER_STATE", f"This command cannot run while the order is {order.status}."
        )


def create(
    workspace: Path,
    platform: Literal["fiverr", "upwork", "direct", "test"] = "direct",
    alias: str = "",
    package: str = "basic",
    currency: str = "USD",
    output_date_format: str = "%m/%d/%Y",
) -> Order:
    now = datetime.now(UTC)
    order_id = f"{now:%Y%m%d}-{platform}-{secrets.token_hex(4)}"
    order = Order(
        order_id=order_id,
        created_at=now,
        platform=platform,
        client_alias=alias,
        package=package,
        currency=currency,
        output_date_format=output_date_format,
        status_history=[Event(status="created", at=now)],
    )
    directory = root(workspace, order_id)
    directory.mkdir(parents=True, exist_ok=False)
    for name in ["input", "work", "review", "output", "delivery"]:
        (directory / name).mkdir()
    save(workspace, order)
    return order


def listing(workspace: Path) -> list[Order]:
    directory = workspace / "orders"
    if not directory.exists():
        return []
    if directory.is_symlink():
        raise StmtconvError("ORDER_PATH", "Orders folder cannot be a symbolic link.")
    return [load(workspace, p.name) for p in sorted(directory.iterdir()) if p.is_dir()]


def json_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StmtconvError("DATA_INVALID", "Expected a JSON object.")
    return value
