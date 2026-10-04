"""Order extraction orchestration and stored statement boundaries."""

from time import perf_counter

import pdfplumber

from stmtconv.config import Settings
from stmtconv.core.models import Statement
from stmtconv.errors import StmtconvError
from stmtconv.extract.base import PageSet
from stmtconv.extract.router import route
from stmtconv.orders import store
from stmtconv.orders.models import StatementFact, Status
from stmtconv.profiles.schema import detect, load_profiles


def read_statements(settings: Settings, order_id: str) -> list[Statement]:
    order = store.load(settings.workspace, order_id)
    directory = store.root(settings.workspace, order_id)
    try:
        return [
            Statement.model_validate_json(
                store.child(directory, f"work/{fact.id}/statement.json").read_text(encoding="utf-8")
            )
            for fact in order.statements
        ]
    except (OSError, ValueError) as exc:
        raise StmtconvError("STATEMENT_READ", "Statement data is missing or invalid.") from exc


def persist(settings: Settings, order_id: str, statements: list[Statement]) -> None:
    directory = store.root(settings.workspace, order_id)
    for statement in statements:
        store.atomic_text(
            store.child(directory, f"work/{statement.id}/statement.json"),
            statement.model_dump_json(indent=2) + "\n",
        )


def page_groups(specification: str | None, count: int) -> list[list[int]]:
    if not specification:
        return [list(range(1, count + 1))]
    groups = []
    try:
        for segment in specification.split(","):
            bounds = [int(v) for v in segment.split("-")]
            if len(bounds) not in {1, 2}:
                raise ValueError
            groups.append(list(range(bounds[0], bounds[-1] + 1)))
        flat = [p for group in groups for p in group]
        if not flat or len(set(flat)) != len(flat) or min(flat) < 1 or max(flat) > count:
            raise ValueError
    except ValueError as exc:
        raise StmtconvError("PAGES_INVALID", "Use distinct page ranges such as 1-4,5-9.") from exc
    return groups


def extract(
    settings: Settings,
    order_id: str,
    profile_id: str | None = None,
    pages: str | None = None,
    engine: str = "text",
    ai: bool = False,
) -> list[Statement]:
    start = perf_counter()
    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"intake_done", "extracted", "needs_review", "reviewed"})
        if not order.files:
            raise StmtconvError("EXTRACT_EMPTY", "Complete intake first.")
        profiles = load_profiles()
        directory = store.root(settings.workspace, order_id)
        statements: list[Statement] = []
        facts = []
        for file in order.files:
            path = store.child(directory, file.work_file)
            with pdfplumber.open(path) as document:
                text = document.pages[0].extract_text() or ""
            profile = detect(text, profiles, profile_id)
            for group in page_groups(pages, len(file.pages)):
                statement_id = f"s{len(statements) + 1:04d}"
                statement = route(
                    statement_id,
                    PageSet(
                        path,
                        file.name,
                        group,
                        any(p.kind == "scanned" for p in file.pages if p.page in group),
                    ),
                    profile,
                    order.date_order,
                    settings.balance_tolerance,
                    settings.date_out_of_period_days,
                    engine,
                )
                statement.summary.currency = order.currency
                statements.append(statement)
                facts.append(
                    StatementFact(
                        id=statement_id,
                        file=file.name,
                        pages=group,
                        profile=profile.id,
                        account_mask=statement.summary.account_mask,
                        verdict=statement.verdict,
                        rows=len(statement.transactions),
                        mismatches=sum(
                            t.check.status == "MISMATCH" for t in statement.transactions
                        ),
                        engines={
                            p: str(d.get("engine", "text"))
                            for p, d in statement.diagnostics.items()
                        },
                    )
                )
        persist(settings, order_id, statements)
        order.statements = facts
        order.timings["extract"] = perf_counter() - start
        order.manual_fixes = 0
        order.spot_check = type(order.spot_check)()
        if order.status == "intake_done":
            store.transition(order, "extracted")
        target: Status = (
            "needs_review"
            if any(s.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"} for s in statements)
            else "reviewed"
        )
        if order.status != target:
            store.transition(order, target)
    return statements


def revalidate(settings: Settings, order_id: str) -> list[Statement]:
    from stmtconv.core.validate import validate

    with store.edit(settings.workspace, order_id) as order:
        store.require(order, {"extracted", "needs_review", "reviewed"})
        statements = [
            validate(s, settings.balance_tolerance) for s in read_statements(settings, order_id)
        ]
        persist(settings, order_id, statements)
        for fact, statement in zip(order.statements, statements, strict=True):
            fact.verdict = statement.verdict
            fact.mismatches = sum(t.check.status == "MISMATCH" for t in statement.transactions)
        target: Status = (
            "needs_review"
            if any(s.verdict in {"NEEDS_REVIEW", "UNVERIFIABLE"} for s in statements)
            else "reviewed"
        )
        if order.status != target:
            store.transition(order, target)
    return statements
