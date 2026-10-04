"""Drop-folder and synthetic demo convenience commands."""

from pathlib import Path

import typer
from rich.console import Console

from stmtconv.cli.support import call
from stmtconv.demo_assets import assets
from stmtconv.launcher import launch


def register(app: typer.Typer) -> None:
    @app.command("inbox")
    def inbox(ctx: typer.Context, folder: Path = Path("inbox")) -> None:
        order_id, message, paths = call(lambda: launch(ctx.obj.settings, ctx.obj.catalog, folder))
        Console().print(f"{order_id}: {message}", markup=False)
        for path in paths:
            Console().print(str(path), markup=False)
        if message != "Delivered":
            raise typer.Exit(2)

    @app.command("demo")
    def demo(ctx: typer.Context, output: Path = Path("workspace/demo")) -> None:
        paths = call(lambda: assets(ctx.obj.settings, ctx.obj.catalog, output))
        for path in paths:
            Console().print(str(path), markup=False)
