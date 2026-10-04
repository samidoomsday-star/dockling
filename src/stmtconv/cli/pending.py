"""Advertise planned commands without pretending they process orders."""

from collections.abc import Callable

import typer
from rich.console import Console

from stmtconv.cli.messages import NOT_IMPLEMENTED


def unavailable(phase: int) -> None:
    Console().print(NOT_IMPLEMENTED.format(phase=phase), markup=False)
    raise typer.Exit(2)


def register(app: typer.Typer) -> None:
    phases = {
        "review": 6,
        "apply-review": 6,
        "spotcheck": 6,
        "export": 6,
        "deliver": 8,
        "close": 8,
        "run": 8,
    }
    for name, phase in phases.items():

        def make_command(target_phase: int) -> Callable[[str], None]:
            def command(
                order_id: str = typer.Argument(..., help="Order ID (not processed yet)."),
            ) -> None:
                unavailable(target_phase)

            return command

        app.command(name, help=f"Planned for Phase {phase}; not implemented yet.")(
            make_command(phase)
        )

    @app.command(help="Anonymous metrics, planned for Phase 8.")
    def stats() -> None:
        unavailable(8)
