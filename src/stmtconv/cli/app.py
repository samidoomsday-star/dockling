"""Argument parsing, service calls and reports only."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from stmtconv import __version__, health, model_setup
from stmtconv.catalog import Catalog, load_catalog
from stmtconv.cli import messages
from stmtconv.cli.pending import register
from stmtconv.config import Settings, load_settings, resolve_config_dir
from stmtconv.errors import StmtconvError
from stmtconv.logging_setup import configure_logging

app = typer.Typer(
    help="Dockling — local statement converter (Phase 1 foundation).", no_args_is_help=True
)
console = Console()


@dataclass
class Runtime:
    settings: Settings
    catalog: Catalog
    logger: logging.Logger


def show_error(exc: StmtconvError) -> None:
    console.print(f"{exc.code}: {exc.message}", markup=False)
    if exc.hint:
        console.print(exc.hint, markup=False)


@app.callback(invoke_without_command=True)
def configure(
    ctx: typer.Context,
    config_dir: Annotated[
        Path | None, typer.Option(help="Folder containing the four configuration YAML files.")
    ] = None,
    env_file: Annotated[
        Path | None, typer.Option(help="Personal .env file (never displayed).")
    ] = None,
    version: Annotated[bool, typer.Option("--version", is_eager=True)] = False,
) -> None:
    if version:
        console.print(f"stmtconv {__version__}: {messages.FOUNDATION}", markup=False)
        raise typer.Exit()
    if ctx.resilient_parsing:
        return
    try:
        directory = resolve_config_dir(config_dir)
        settings = load_settings(directory, env_file)
        catalog = load_catalog(directory)
        health.prepare_workspace(settings.workspace)
        logger = configure_logging(settings.workspace, settings.log_level)
        ctx.obj = Runtime(settings, catalog, logger)
    except StmtconvError as exc:
        show_error(exc)
        raise typer.Exit(1) from exc
    except OSError as exc:
        console.print(messages.SETUP_FAILED, markup=False)
        raise typer.Exit(1) from exc


@app.command(help="Check local setup, workspace, models and privacy reminders.")
def doctor(ctx: typer.Context) -> None:
    runtime: Runtime = ctx.obj
    try:
        checks = health.inspect(runtime.settings)
    except StmtconvError as exc:
        show_error(exc)
        raise typer.Exit(1) from exc
    table = Table("Check", "Status", "Details")
    for check in checks:
        table.add_row(check.name, check.status, check.detail)
    console.print(table)
    if any(check.status == "FAIL" for check in checks):
        raise typer.Exit(1)


models = typer.Typer(
    help="Local model setup; downloads use the network explicitly.", no_args_is_help=True
)
app.add_typer(models, name="models")


@models.command("download", help="Download public models and verify the pinned artifact hashes.")
def download_models(ctx: typer.Context) -> None:
    runtime: Runtime = ctx.obj
    try:
        model_setup.download(runtime.settings)
    except StmtconvError as exc:
        show_error(exc)
        raise typer.Exit(1) from exc
    console.print(messages.MODELS_READY, markup=False)


register(app)


def main() -> None:
    app()
