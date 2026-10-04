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
        "intake": 2,
        "quote": 2,
        "extract": 4,
        "validate": 4,
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

    @app.command(help="Full pipeline test, planned for Phase 4.")
    def selftest() -> None:
        unavailable(4)

    @app.command(help="Anonymous metrics, planned for Phase 8.")
    def stats() -> None:
        unavailable(8)

    orders = typer.Typer(help="Order management (Phase 2).", no_args_is_help=True)
    app.add_typer(orders, name="order")

    @orders.command("new")
    def order_new(platform: str = "direct", alias: str = "", package: str = "basic") -> None:
        unavailable(2)

    @orders.command("list")
    def order_list() -> None:
        unavailable(2)

    @orders.command("show")
    def order_show(order_id: str) -> None:
        unavailable(2)

    profiles = typer.Typer(help="Layout profiles (Phase 4).", no_args_is_help=True)
    app.add_typer(profiles, name="profile")

    @profiles.command("scaffold")
    def profile_scaffold(order_id: str, file: str) -> None:
        unavailable(4)

    @profiles.command("test")
    def profile_test(profile: str, pdf: str) -> None:
        unavailable(4)
