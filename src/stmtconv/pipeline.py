"""Resumable operator workflow; never implicitly bypass review or export gates."""

from pathlib import Path

from stmtconv.catalog import Catalog
from stmtconv.config import Settings
from stmtconv.export.delivery import deliver
from stmtconv.export.service import export
from stmtconv.extract.service import extract
from stmtconv.intake.service import intake
from stmtconv.orders import store
from stmtconv.review.service import write


def run(
    settings: Settings,
    catalog: Catalog,
    order_id: str,
    skip_spotcheck: bool = False,
    profile: str | None = None,
) -> tuple[str, list[Path]]:
    order = store.load(settings.workspace, order_id)
    if order.status == "created":
        intake(settings, order_id)
        order = store.load(settings.workspace, order_id)
    if order.status == "intake_done":
        extract(settings, order_id, profile_id=profile)
        order = store.load(settings.workspace, order_id)
    if order.status == "needs_review":
        return "Review required", write(settings, order_id)
    if order.status == "reviewed":
        if order.spot_check.passed is not True and not skip_spotcheck:
            return "Run spotcheck, then run again", []
        export(
            settings,
            order_id,
            catalog.exports,
            skip_spotcheck=skip_spotcheck,
            categories=catalog.categories,
        )
        order = store.load(settings.workspace, order_id)
    if order.status in {"exported", "delivered"}:
        return "Delivered", [deliver(settings, order_id)]
    return f"Order is {order.status}", []
