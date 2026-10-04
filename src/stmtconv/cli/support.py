"""Safe command error boundary; no client values or tracebacks in operator errors."""

from collections.abc import Callable

import typer
from rich.console import Console

from stmtconv.errors import StmtconvError


def call[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except StmtconvError as exc:
        Console().print(f"{exc.code}: {exc.message}", markup=False)
        if exc.hint:
            Console().print(exc.hint, markup=False)
        raise typer.Exit(1) from None
    except (OSError, ValueError) as exc:
        Console().print(
            "COMMAND_FAILED: Check the order files and settings. Input values are hidden.",
            markup=False,
        )
        raise typer.Exit(1) from exc
