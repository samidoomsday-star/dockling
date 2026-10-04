"""Export gates and staged publication of complete output sets."""

import shutil
import tempfile
from pathlib import Path
from time import perf_counter

from stmtconv.catalog import Exports
from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.export import csv_writer, excel
from stmtconv.extract.service import read_statements
from stmtconv.orders import store


def export(
    settings: Settings,
    order_id: str,
    specs: Exports,
    allow_unverified: bool = False,
    skip_spotcheck: bool = False,
    accept_unverifiable: bool = False,
) -> list[Path]:
    started = perf_counter()
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"needs_review", "reviewed", "exported"})
        statements = read_statements(settings, order_id)
        if not statements:
            raise StmtconvError("EXPORT_EMPTY", "Extract statements before export.")
        if any(s.verdict == "NEEDS_REVIEW" for s in statements) and not allow_unverified:
            raise StmtconvError(
                "EXPORT_BLOCKED_UNVERIFIED",
                "Resolve flagged statements or explicitly use --allow-unverified.",
            )
        if any(s.verdict == "UNVERIFIABLE" for s in statements) and not accept_unverifiable:
            raise StmtconvError(
                "EXPORT_UNVERIFIABLE",
                "Explicitly use --accept-unverifiable to acknowledge missing verification evidence.",
            )
        if order.spot_check.passed is not True and not skip_spotcheck:
            raise StmtconvError(
                "EXPORT_SPOTCHECK",
                "A passed spot-check is required.",
                "Run spotcheck, or explicitly use --skip-spotcheck.",
            )
        if "ofx" in order.outputs:
            raise StmtconvError("EXPORT_NOT_READY", "OFX is implemented in Phase 7.")
        directory = store.root(settings.workspace, order_id)
        staging = Path(tempfile.mkdtemp(prefix="export-", dir=store.child(directory, "work")))
        names = []
        try:
            for statement in statements:
                from re import sub

                account = sub(r"[^a-zA-Z0-9_-]", "", statement.summary.account_mask or "unknown")[
                    -8:
                ]
                period = (
                    statement.summary.period_start.strftime("%Y%m")
                    if statement.summary.period_start
                    else "unknown"
                )
                stem = f"{order_id}-{statement.id}-{account}-{period}"
                for format_name in order.outputs:
                    spec = specs.formats[format_name]
                    if format_name == "excel":
                        path = staging / f"{stem}.xlsx"
                        excel.write(
                            statement,
                            path,
                            spec,
                            statement.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"},
                            order.categorize,
                            skip_spotcheck,
                            order.output_date_format,
                        )
                        names.append(path.name)
                    else:
                        limit = (
                            settings.qb_csv_max_rows
                            if format_name.startswith("qb_")
                            else max(len(statement.transactions), 1)
                        )
                        groups = [
                            statement.transactions[i : i + limit]
                            for i in range(0, len(statement.transactions), limit)
                        ]
                        for index, rows in enumerate(groups, 1):
                            suffix = f"-part{index}" if len(groups) > 1 else ""
                            path = staging / f"{stem}-{format_name}{suffix}.csv"
                            date_format = (
                                "%Y-%m-%d" if format_name == "csv" else order.output_date_format
                            )
                            path.write_bytes(
                                csv_writer.serialize(
                                    statement, spec, date_format, rows, format_name == "csv"
                                )
                            )
                            names.append(path.name)
            output = store.child(directory, "output")
            previous = staging.parent / (staging.name + "-previous")
            output.rename(previous)
            try:
                staging.rename(output)
            except OSError:
                previous.rename(output)
                raise
            shutil.rmtree(previous)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        order.exported_unverified = any(
            s.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"} for s in statements
        )
        order.spot_check.skipped = skip_spotcheck
        order.timings["export"] = perf_counter() - started
        if order.status == "needs_review":
            store.transition(order, "reviewed")
        if order.status != "exported":
            store.transition(order, "exported")
    return [store.root(settings.workspace, order_id) / "output" / name for name in names]
