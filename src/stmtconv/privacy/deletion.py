"""Verified local deletion; partial failures cannot produce a success certificate."""

import hashlib
import os
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.export.templates import render
from stmtconv.extract.service import read_statements
from stmtconv.orders import ledger, store
from stmtconv.orders.models import Order


def inventory(directory: Path) -> list[Path]:
    paths = []

    def fail(error: OSError) -> None:
        raise error

    for base, directories, files in os.walk(directory, followlinks=False, onerror=fail):
        for name in [*directories, *files]:
            path = Path(base) / name
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise StmtconvError(
                    "DELETION_PATH", "Refusing deletion through a symbolic link or escaped path."
                )
            if path.is_file() and (
                path.parent != directory or path.name not in {"order.json", ".lock"}
            ):
                paths.append(path)
    return paths


def metrics(settings: Settings, order: Order) -> ledger.Metrics:
    try:
        statements = read_statements(settings, order.order_id)
    except StmtconvError:
        statements = []  # Cleanup must remain possible for damaged/abandoned artifacts.
    engines = Counter(engine for fact in order.statements for engine in fact.engines.values())
    samples: dict[str, list[float]] = {"text": [], "scanned": []}
    for statement in statements:
        for page, diagnostic in statement.diagnostics.items():
            fact = next(f for f in order.statements if f.id == statement.id)
            original_file = next(f for f in order.files if f.name == fact.file)
            kind = next(p.kind for p in original_file.pages if p.page == int(page))
            seconds = diagnostic.get("seconds")
            if kind in samples and isinstance(seconds, (int, float)) and seconds > 0:
                samples[kind].append(float(seconds))
    return ledger.Metrics(
        outcome="abandoned" if order.status == "failed" else "delivered",
        order_id=order.order_id,
        platform=order.platform,
        package=order.package,
        pages_by_kind=order.pages_by_kind,
        statements=len(statements),
        engines=dict(engines),
        seconds_per_stage={
            k: v
            for k, v in order.timings.items()
            if k in {"intake", "extract", "review", "export", "delivery", "close"}
        },
        seconds_per_page={k: sum(v) / len(v) for k, v in samples.items() if v},
        verdicts=dict(Counter(s.verdict for s in statements)),
        manual_fixes=order.manual_fixes,
        review_minutes=order.timings.get("review", 0) / 60,
        ai_pages_used=order.ai_pages_used,
    )


def close(settings: Settings, order_id: str, abandon: bool = False) -> dict[str, object]:
    with store.edit(settings.workspace, order_id) as order:
        if order.status == "closed":
            ledger.append(settings.workspace, ledger.Metrics.model_validate(order.metrics))
            return order.deletion_certificate or {}
        if order.status != "delivered":
            if not abandon:
                raise StmtconvError(
                    "CLOSE_UNDELIVERED", "Use --abandon explicitly to remove an unfinished order."
                )
            if order.status != "failed":
                store.transition(order, "failed", "OPERATOR_ABANDONED")
        directory = store.root(settings.workspace, order_id)
        paths = inventory(directory)
        if not order.deletion_pending:
            order.metrics = metrics(settings, order).model_dump(mode="json")
        retained = {str(item["filename_sha256"]): item for item in order.deletion_inventory}
        for path in paths:
            name_hash = hashlib.sha256(path.relative_to(directory).as_posix().encode()).hexdigest()
            retained[name_hash] = {
                "filename_sha256": name_hash,
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        order.deletion_inventory = list(retained.values())
        order.deletion_pending = True
        store.save(settings.workspace, order)
        try:
            for path in list(directory.iterdir()):
                if path.name in {"order.json", ".lock"}:
                    continue
                store.child(directory, path.name)
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            if inventory(directory):
                raise OSError("Client files remain")
            if {p.name for p in directory.iterdir()} - {"order.json", ".lock"}:
                raise OSError("Order artifacts remain")
        except OSError as exc:
            order.error_code = "DELETION_PARTIAL"
            store.save(settings.workspace, order)
            raise StmtconvError(
                "DELETION_PARTIAL",
                "Some local files could not be removed; no success certificate was issued.",
                "Close programs using the files, then retry close.",
            ) from exc
        now = datetime.now(UTC)
        certificate: dict[str, object] = {
            "order_id": order_id,
            "deleted_at": now.isoformat(),
            "files": order.deletion_inventory,
            "text": render(
                "deletion_certificate.md",
                {
                    "order_id": order_id,
                    "deleted_at": now.isoformat(),
                    "files": len(order.deletion_inventory),
                },
            ),
        }
        anonymous = Order(
            order_id=order.order_id,
            created_at=order.created_at,
            platform=order.platform,
            package=order.package,
            currency=order.currency,
            status=order.status,
            status_history=order.status_history,
            pages_by_kind=order.pages_by_kind,
            manual_fixes=order.manual_fixes,
            timings={
                k: v
                for k, v in order.timings.items()
                if k in {"intake", "extract", "review", "export", "delivery", "close"}
            },
            metrics=order.metrics,
            deleted_at=now,
            deletion_certificate=certificate,
        )
        store.transition(anonymous, "closed")
        # Mutate the edit context's record, so its final save cannot restore client fields.
        for name in Order.model_fields:
            setattr(order, name, getattr(anonymous, name))
        store.save(settings.workspace, order)
        ledger.append(settings.workspace, ledger.Metrics.model_validate(order.metrics))
    return certificate
