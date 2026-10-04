"""Export gates and staged publication of complete output sets."""

import shutil
import tempfile
from pathlib import Path
from time import perf_counter

from stmtconv.catalog import Categories, Exports
from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.export import csv_writer, excel, merged, ofx
from stmtconv.extract.service import persist, read_statements
from stmtconv.orders import store


def export(
    settings: Settings,
    order_id: str,
    specs: Exports,
    allow_unverified: bool = False,
    skip_spotcheck: bool = False,
    accept_unverifiable: bool = False,
    categories: Categories | None = None,
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
        from stmtconv.core.categorize import Rule, categorize
        from stmtconv.core.merge import merge

        directory = store.root(settings.workspace, order_id)
        if order.categorize:
            from stmtconv.config import read_yaml

            rules = list((categories or Categories(rules=[])).rules)
            override = store.child(directory, "categories.yaml")
            if override.is_file():
                rules = [*Categories.model_validate(read_yaml(override)).rules, *rules]
            statements = [
                categorize(
                    statement, [Rule(rule.category, rule.match, rule.direction) for rule in rules]
                )
                for statement in statements
            ]
        if order.account_group and order.account_confirmed:
            import hashlib

            identity = hashlib.sha256(("operator:" + order.account_group).encode()).hexdigest()
            for statement in statements:
                if statement.summary.account_key is None:
                    statement.summary.account_key = identity
        combination = (
            merge(
                statements,
                settings.balance_tolerance,
                order.account_group if order.account_confirmed else None,
            )
            if order.merge
            else None
        )
        if combination is not None:
            if any(
                i.code in {"ACCOUNT_GROUP_UNKNOWN", "ACCOUNT_IDENTITY_UNCONFIRMED"}
                for i in combination.issues
            ):
                raise StmtconvError(
                    "MERGE_ACCOUNT",
                    "Merge requires one known account, currency and account direction.",
                )
            if combination.issues and not allow_unverified:
                raise StmtconvError(
                    "MERGE_CONTINUITY",
                    "Resolve merge continuity/period issues or use --allow-unverified.",
                )
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
                    elif format_name == "ofx":
                        path = staging / f"{stem}.ofx"
                        path.write_bytes(
                            ofx.serialize(statement, order.created_at.strftime("%Y%m%d%H%M%S"))
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
            if combination is not None:
                path = staging / f"{order_id}-merged.xlsx"
                merged.write(combination, path)
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
        persist(settings, order_id, statements)
        order.merge_issues = (
            [i.model_dump(mode="json") for i in combination.issues] if combination else []
        )
        order.exported_unverified = bool(order.merge_issues) or any(
            s.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"} for s in statements
        )
        order.spot_check.skipped = skip_spotcheck
        order.timings["export"] = perf_counter() - started
        if order.status == "needs_review":
            store.transition(order, "reviewed")
        if order.status != "exported":
            store.transition(order, "exported")
    return [store.root(settings.workspace, order_id) / "output" / name for name in names]
