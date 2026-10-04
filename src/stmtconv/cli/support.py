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
    except (OSError, ValueError):
        Console().print(
            "COMMAND_FAILED: Check the order files and settings. Input values are hidden.",
            markup=False,
        )
        raise typer.Exit(1) from None
    except Exception as exc:
        import logging

        logging.getLogger("stmtconv").error(
            "Unexpected command failure", extra={"error_type": type(exc).__name__}
        )
        Console().print(
            "COMMAND_FAILED: Could not complete this command. Report this code; private details are hidden.",
            markup=False,
        )
        raise typer.Exit(1) from None
