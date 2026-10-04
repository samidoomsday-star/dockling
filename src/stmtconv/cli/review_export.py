"""Review, spot-check and export command arguments and reports."""

import typer
from rich.console import Console
from rich.table import Table

from stmtconv.cli.extraction import report
from stmtconv.cli.support import call
from stmtconv.export.service import export
from stmtconv.review import service


def register(app: typer.Typer) -> None:
    @app.command("review")
    def review(ctx: typer.Context, order_id: str) -> None:
        paths = call(lambda: service.write(ctx.obj.settings, order_id))
        for path in paths:
            Console().print(str(path), markup=False)

    @app.command("apply-review")
    def apply_review(ctx: typer.Context, order_id: str, confirm_ai_source: bool = False) -> None:
        report(call(lambda: service.apply(ctx.obj.settings, order_id, confirm_ai_source)))

    @app.command("spotcheck")
    def spotcheck(ctx: typer.Context, order_id: str) -> None:
        rows = call(lambda: service.sample(ctx.obj.settings, order_id))
        table = Table("Row ID", "Page", "Date", "Description", "Debit", "Credit", "Balance")
        for row in rows:
            table.add_row(
                row.id,
                str(row.page),
                str(row.date),
                row.description,
                str(row.debit or ""),
                str(row.credit or ""),
                str(row.balance if row.balance is not None else ""),
            )
        Console().print(table)
        passed = typer.confirm("Did every sampled row match its source page?")
        note = typer.prompt("Spot-check note", default="")
        call(lambda: service.record_spotcheck(ctx.obj.settings, order_id, passed, note))
        if not passed:
            raise typer.Exit(1)

    @app.command("export")
    def export_command(
        ctx: typer.Context,
        order_id: str,
        allow_unverified: bool = False,
        skip_spotcheck: bool = False,
        accept_unverifiable: bool = False,
    ) -> None:
        paths = call(
            lambda: export(
                ctx.obj.settings,
                order_id,
                ctx.obj.catalog.exports,
                allow_unverified,
                skip_spotcheck,
                accept_unverifiable,
                ctx.obj.catalog.categories,
            )
        )
        for path in paths:
            Console().print(str(path), markup=False)
