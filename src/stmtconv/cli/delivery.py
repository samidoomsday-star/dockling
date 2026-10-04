"""Delivery, closure and resumable workflow reports."""

import json

import typer
from rich.console import Console

from stmtconv.cli.support import call
from stmtconv.export.delivery import deliver
from stmtconv.orders.ledger import stats
from stmtconv.pipeline import run
from stmtconv.privacy.deletion import close


def register(app: typer.Typer) -> None:
    @app.command("deliver")
    def deliver_command(ctx: typer.Context, order_id: str) -> None:
        path = call(lambda: deliver(ctx.obj.settings, order_id))
        Console().print(str(path), markup=False)

    @app.command("close")
    def close_command(
        ctx: typer.Context, order_id: str, yes: bool = False, abandon: bool = False
    ) -> None:
        if not yes and not typer.confirm(
            "Remove this order’s local input, review, output and delivery files?"
        ):
            raise typer.Exit(2)
        result = call(lambda: close(ctx.obj.settings, order_id, abandon))
        Console().print(str(result.get("text", "")), markup=False)

    @app.command("stats")
    def stats_command(ctx: typer.Context) -> None:
        Console().print(
            json.dumps(call(lambda: stats(ctx.obj.settings.workspace)), indent=2), markup=False
        )

    @app.command("run")
    def run_command(
        ctx: typer.Context, order_id: str, skip_spotcheck: bool = False, profile: str | None = None
    ) -> None:
        message, paths = call(
            lambda: run(ctx.obj.settings, ctx.obj.catalog, order_id, skip_spotcheck, profile)
        )
        Console().print(message, markup=False)
        for path in paths:
            Console().print(str(path), markup=False)
        if message != "Delivered":
            raise typer.Exit(2)
