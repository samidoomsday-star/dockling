"""Extraction/profile CLI surfaces; all processing is in services."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from stmtconv.cli.support import call
from stmtconv.core.models import Statement
from stmtconv.extract import service
from stmtconv.selftest import run


def report(statements: list[Statement]) -> None:
    table = Table("Statement", "Rows", "Mismatches", "Verdict")
    for statement in statements:
        table.add_row(
            statement.id,
            str(len(statement.transactions)),
            str(sum(t.check.status == "MISMATCH" for t in statement.transactions)),
            statement.verdict,
        )
    Console().print(table)


def register(app: typer.Typer) -> None:
    @app.command("extract")
    def extract(
        ctx: typer.Context,
        order_id: str,
        profile: str | None = None,
        pages: str | None = None,
        engine: str = "auto",
        ai: bool = False,
    ) -> None:
        report(
            call(lambda: service.extract(ctx.obj.settings, order_id, profile, pages, engine, ai))
        )

    @app.command("validate")
    def validate(ctx: typer.Context, order_id: str) -> None:
        report(call(lambda: service.revalidate(ctx.obj.settings, order_id)))

    @app.command("selftest")
    def selftest(ctx: typer.Context) -> None:
        result = call(lambda: run(ctx.obj.settings))
        Console().print(json.dumps(result, indent=2), markup=False)
        if not result["passed"]:
            raise typer.Exit(1)

    profiles = typer.Typer(help="Author and check statement-layout profiles.", no_args_is_help=True)
    app.add_typer(profiles, name="profile")

    @profiles.command("test")
    def test(ctx: typer.Context, profile: str, pdf: Path) -> None:
        import pdfplumber

        from stmtconv.extract.base import PageSet
        from stmtconv.extract.router import route
        from stmtconv.profiles.schema import detect, load_profiles

        def action() -> Statement:
            with pdfplumber.open(pdf) as doc:
                pages = list(range(1, len(doc.pages) + 1))
            return route(
                "profile-test",
                PageSet(pdf, pdf.name, pages),
                detect("", load_profiles(), profile),
                "auto",
                ctx.obj.settings.balance_tolerance,
                ctx.obj.settings.date_out_of_period_days,
            )

        report([call(action)])

    @profiles.command("scaffold")
    def scaffold(ctx: typer.Context, order_id: str, file: str) -> None:
        from stmtconv.profiles.service import scaffold

        path = call(lambda: scaffold(ctx.obj.settings.workspace, order_id, file))
        Console().print(str(path), markup=False)
