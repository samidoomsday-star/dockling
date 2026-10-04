"""Order/intake argument parsing and reports."""

from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table

from stmtconv.cli.support import call
from stmtconv.intake.quote import quote
from stmtconv.intake.service import intake
from stmtconv.orders import store


def register(app: typer.Typer) -> None:
    orders = typer.Typer(help="Create and inspect local jobs.", no_args_is_help=True)
    app.add_typer(orders, name="order")

    @orders.command("new")
    def new(
        ctx: typer.Context,
        platform: Literal["fiverr", "upwork", "direct", "test"] = "direct",
        alias: str = "",
        package: str = "basic",
        date_order: Literal["auto", "DMY", "MDY", "YMD"] = "auto",
        outputs: str = "excel,csv",
        merge: bool = False,
        account_group: str | None = None,
        confirm_account: bool = False,
        categorize: bool = False,
    ) -> None:
        runtime = ctx.obj

        def action() -> str:
            from stmtconv.errors import StmtconvError
            from stmtconv.orders.models import Output

            if package not in {p.name for p in runtime.catalog.pricing.packages}:
                raise StmtconvError("ORDER_PACKAGE", "Unknown package name.")
            # Validate all requested values before making a folder.
            from pydantic import TypeAdapter

            selected = TypeAdapter(list[Output]).validate_python(outputs.split(","))
            order = store.create(
                runtime.settings.workspace,
                platform,
                alias,
                package,
                runtime.settings.default_currency,
                runtime.settings.output_date_format,
            )
            with store.edit(runtime.settings.workspace, order.order_id) as edited:
                edited.date_order = date_order
                edited.outputs = selected
                edited.merge = merge
                edited.account_group = account_group
                edited.account_confirmed = confirm_account
                edited.categorize = categorize
            return order.order_id

        order_id = call(action)
        Console().print(f"Created {order_id}")
        Console().print(
            str(store.root(runtime.settings.workspace, order_id) / "input"), markup=False
        )

    @orders.command("list")
    def listing(ctx: typer.Context, overdue: bool = False) -> None:
        records = call(lambda: store.listing(ctx.obj.settings.workspace))
        table = Table("Order", "Status", "Pages")
        for order in records:
            if overdue:
                from datetime import UTC, datetime

                delivered = [e.at for e in order.status_history if e.status == "delivered"]
                if (
                    order.status != "delivered"
                    or not delivered
                    or (datetime.now(UTC) - delivered[-1]).days
                    <= ctx.obj.settings.retention_days_after_delivery
                ):
                    continue
            table.add_row(order.order_id, order.status, str(sum(order.pages_by_kind.values())))
        Console().print(table)

    @orders.command("show")
    def show(ctx: typer.Context, order_id: str) -> None:
        order = call(lambda: store.load(ctx.obj.settings.workspace, order_id))
        Console().print(order.model_dump_json(indent=2), markup=False)

    @app.command("intake")
    def intake_command(
        ctx: typer.Context,
        order_id: str,
        password: Annotated[
            bool, typer.Option(help="Prompt privately for a PDF password.")
        ] = False,
        combine: bool = False,
        force: bool = False,
    ) -> None:
        secret = typer.prompt("PDF password", hide_input=True) if password else None
        files = call(lambda: intake(ctx.obj.settings, order_id, secret, combine, force))
        table = Table("File", "Pages", "Text", "Scanned", "Blank")
        for file in files:
            table.add_row(
                file.name,
                str(len(file.pages)),
                *(str(sum(p.kind == k for p in file.pages)) for k in ["text", "scanned", "blank"]),
            )
        Console().print(table)
        quote_command(ctx, order_id)

    @app.command("quote")
    def quote_command(ctx: typer.Context, order_id: str) -> None:
        result = call(
            lambda: quote(
                store.load(ctx.obj.settings.workspace, order_id),
                ctx.obj.catalog.pricing,
                ctx.obj.settings,
            )
        )
        Console().print(
            f"{result.package}: {result.pages} pages; {result.price_min}–{result.price_max}; estimated processing {result.seconds:.1f}s; add-ons {', '.join(result.addons) or 'none'}",
            markup=False,
        )
