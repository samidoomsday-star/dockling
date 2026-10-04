"""Guided BYOK choices; secrets are entered privately and never displayed."""

from typing import Literal

import typer
from pydantic import SecretStr, TypeAdapter
from rich.console import Console
from rich.table import Table

from stmtconv.ai import providers
from stmtconv.ai.providers import Effort, Provider
from stmtconv.cli.support import call
from stmtconv.extract.ai_engine import discover
from stmtconv.orders import store


def register(app: typer.Typer) -> None:
    ai = typer.Typer(help="Optional private OpenAI-compatible BYOK setup.", no_args_is_help=True)
    app.add_typer(ai, name="ai")

    @ai.command("setup")
    def setup(ctx: typer.Context) -> None:
        name = typer.prompt("Provider nickname (letters, digits, underscore or hyphen)")
        url = typer.prompt("OpenAI-compatible base URL, including /v1 if required")
        key = typer.prompt(
            "Your API key (blank only for a keyless local endpoint)",
            hide_input=True,
            default="",
            show_default=False,
        )
        terms = typer.confirm(
            "Have you checked that this provider’s data-handling terms are suitable for your client data?",
            default=False,
        )
        style = typer.prompt("API style: chat or responses", default="chat")
        native = typer.prompt(
            "JSON mode: prompt_json, json_object or json_schema", default="prompt_json"
        )
        effort_style = typer.prompt(
            "Effort parameter: reasoning_effort, reasoning or none",
            default="reasoning_effort" if style == "chat" else "reasoning",
        )
        provider = call(
            lambda: Provider(
                name=name,
                base_url=url,
                api_key=SecretStr(key) if key else None,
                requires_key=bool(key),
                terms_confirmed=terms,
                api_style=style,
                schema_style=native,
                effort_style=effort_style,
                completion_route="/responses" if style == "responses" else "/chat/completions",
                token_field="max_output_tokens" if style == "responses" else "max_tokens",
            )
        )
        existing = providers.load(ctx.obj.settings.workspace)
        if any(p.name == name for p in existing.providers) and not typer.confirm(
            "Replace this provider’s saved settings?", default=False
        ):
            raise typer.Exit(2)
        call(lambda: providers.update(ctx.obj.settings.workspace, provider))
        if typer.confirm(
            "Discover models now? This contacts your endpoint without transaction data.",
            default=False,
        ):
            provider.models = call(lambda: discover(provider))
            call(lambda: providers.update(ctx.obj.settings.workspace, provider))
        pick(ctx, name)

    @ai.command("list")
    def listing(ctx: typer.Context) -> None:
        settings = call(lambda: providers.load(ctx.obj.settings.workspace))
        table = Table("Provider", "Selected", "Model", "Effort", "Key configured")
        for provider in settings.providers:
            table.add_row(
                provider.name,
                str(provider.name == settings.selected),
                provider.selected_model or "",
                provider.effort,
                str(bool(provider.api_key)),
            )
        Console().print(table)

    @ai.command("models")
    def models(ctx: typer.Context, provider: str) -> None:
        chosen = call(lambda: providers.get(ctx.obj.settings.workspace, provider))
        chosen.models = call(lambda: discover(chosen))
        call(lambda: providers.update(ctx.obj.settings.workspace, chosen))
        table = Table("Model", "Advertised effort choices")
        for model in chosen.models:
            table.add_row(model.id, ", ".join(model.efforts))
        Console().print(table)

    @ai.command("pick")
    def pick(
        ctx: typer.Context,
        provider: str,
        model: str | None = None,
        effort: str | None = None,
        manual: bool = False,
    ) -> None:
        chosen = call(lambda: providers.get(ctx.obj.settings.workspace, provider))
        if model is None:
            for index, candidate in enumerate(chosen.models, 1):
                Console().print(f"{index}. {candidate.id}", markup=False)
            entry = typer.prompt("Model ID, list number, or a manual model ID")
            if entry.isdigit() and 1 <= int(entry) <= len(chosen.models):
                model = chosen.models[int(entry) - 1].id
            else:
                model = entry
                manual = not any(m.id == model for m in chosen.models)
        selected = next((m for m in chosen.models if m.id == model), None)
        choices: list[Effort] = selected.efforts if selected else ["provider_default"]
        if effort is None:
            for index, value in enumerate(choices, 1):
                label = (
                    f"Max ({selected.capability_source if selected else 'unknown'})"
                    if value == "max"
                    else value
                )
                Console().print(f"{index}. {label}", markup=False)
            rank = ["provider_default", "minimal", "low", "medium", "high", "xhigh", "max"]
            highest = max(choices, key=lambda value: rank.index(value))
            entry = typer.prompt(
                "Effort choice number (default: highest supported)",
                default=str(choices.index(highest) + 1),
            )
            if not entry.isdigit() or not 1 <= int(entry) <= len(choices):
                Console().print("Choose one of the displayed effort numbers.")
                raise typer.Exit(1)
            effort = choices[int(entry) - 1]
        requested: Effort = call(lambda: TypeAdapter(Effort).validate_python(effort))
        result = call(lambda: providers.choose(chosen, str(model), requested, manual))
        call(lambda: providers.update(ctx.obj.settings.workspace, result, select=True))
        Console().print(
            f"Selected {result.name}: {result.selected_model}; effort {result.effort}. AI remains off until explicitly activated for a consented order.",
            markup=False,
        )

    @ai.command("capabilities")
    def capabilities(
        ctx: typer.Context, provider: str, model: str, efforts: str, reference: str
    ) -> None:
        chosen = call(lambda: providers.get(ctx.obj.settings.workspace, provider))
        levels: list[Effort] = call(
            lambda: TypeAdapter(list[Effort]).validate_python(efforts.split(","))
        )
        if not reference.strip() or not typer.confirm(
            "Have you verified these exact effort levels for this model in the provider documentation?",
            default=False,
        ):
            raise typer.Exit(2)
        existing = next((m for m in chosen.models if m.id == model), None)
        if existing is None:
            from stmtconv.ai.providers import Model

            existing = Model(id=model, manual=True)
            chosen.models.append(existing)
        existing.efforts = list(dict.fromkeys(["provider_default", *levels]))
        existing.capability_source = "operator_documentation"
        existing.capability_reference = reference
        call(lambda: providers.update(ctx.obj.settings.workspace, chosen))
        Console().print(
            "Model-specific documentation choices saved. A rejected effort will still fail without downgrading."
        )

    @ai.command("test")
    def test(ctx: typer.Context, provider: str) -> None:
        chosen = call(lambda: providers.get(ctx.obj.settings.workspace, provider))
        models = call(lambda: discover(chosen))
        Console().print(
            f"Connection and model discovery passed ({len(models)} models). No transaction data was sent."
        )

    @ai.command("adapter")
    def adapter(
        ctx: typer.Context,
        provider: str,
        schema: Literal["prompt_json", "json_object", "json_schema"] = "prompt_json",
        effort_style: Literal["reasoning_effort", "reasoning", "none"] = "reasoning_effort",
        token_field: Literal[
            "max_tokens", "max_completion_tokens", "max_output_tokens"
        ] = "max_tokens",
        completion_route: str | None = None,
        models_route: str | None = None,
        temperature_zero: bool = False,
    ) -> None:
        chosen = call(lambda: providers.get(ctx.obj.settings.workspace, provider))
        data = chosen.model_dump()
        data.update(
            {
                "schema_style": schema,
                "effort_style": effort_style,
                "token_field": token_field,
                "temperature_zero": temperature_zero,
            }
        )
        if completion_route:
            data["completion_route"] = completion_route
        if models_route:
            data["models_route"] = models_route
        updated = call(lambda: Provider.model_validate(data))
        call(lambda: providers.update(ctx.obj.settings.workspace, updated))
        Console().print(
            "Explicit adapter settings saved. No provider/model/effort was silently changed."
        )

    @app.command("ai-consent")
    def consent(ctx: typer.Context, order_id: str, grant: bool = False, note: str = "") -> None:
        from stmtconv.errors import StmtconvError

        def action() -> None:
            with store.edit(ctx.obj.settings.workspace, order_id) as order:
                store.require(
                    order, {"created", "intake_done", "extracted", "needs_review", "reviewed"}
                )
                if grant and not note.strip():
                    raise StmtconvError(
                        "AI_CONSENT_NOTE",
                        "A grant requires a note recording where and when the client agreed.",
                    )
                order.ai_consent = "granted" if grant else "none"
                order.ai_consent_note = note if grant else ""
                order.ai_provider_binding = None

        call(action)
        Console().print("Consent recorded; AI is still only used with extract --ai.")
