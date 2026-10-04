"""Order binding and persisted AI budget; neither values nor credentials are logged."""

import hashlib
import json
from collections.abc import Callable

from stmtconv.ai import providers
from stmtconv.config import Settings
from stmtconv.core.models import Statement
from stmtconv.errors import StmtconvError
from stmtconv.extract.ai_engine import extract
from stmtconv.extract.base import ExtractionResult
from stmtconv.orders import store
from stmtconv.orders.models import Order
from stmtconv.privacy.ai_gate import Gate, check


def callback(
    settings: Settings, order: Order, source_file: str
) -> Callable[[Statement, ExtractionResult], ExtractionResult]:
    provider = providers.get(settings.workspace, settings.ai_provider)
    if provider.api_key is None and settings.ai_api_key is not None:
        provider = provider.model_copy(update={"api_key": settings.ai_api_key}, deep=True)
    from pydantic import TypeAdapter

    from stmtconv.ai.providers import Effort

    requested: Effort = TypeAdapter(Effort).validate_python(settings.ai_effort)
    if settings.ai_model:
        provider = providers.choose(provider, settings.ai_model, requested, manual=False)
    elif settings.ai_effort != "provider_default":
        provider = providers.choose(provider, provider.selected_model or "", requested)

    def gate() -> Gate:
        return Gate(
            True,
            order.ai_consent,
            order.ai_consent_note,
            provider.terms_confirmed,
            bool(provider.selected_model),
            bool(provider.api_key and provider.api_key.get_secret_value()),
            provider.requires_key,
            order.ai_pages_used,
            settings.ai_max_pages_per_order,
        )

    check(gate(), 1)
    binding = hashlib.sha256(
        json.dumps(
            {
                "url": provider.base_url,
                "model": provider.selected_model,
                "effort": provider.effort,
                "style": provider.api_style,
                "schema": provider.schema_style,
                "route": provider.completion_route,
                "effort_style": provider.effort_style,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if order.ai_provider_binding and order.ai_provider_binding != binding:
        raise StmtconvError(
            "AI_PROVIDER_CHANGED",
            "Provider/model/effort changed for this order; record consent again explicitly.",
        )

    def consume() -> None:
        check(gate(), 1)
        order.ai_pages_used += 1
        order.ai_provider_binding = binding
        store.save(settings.workspace, order)

    def run(candidate: Statement, raw: ExtractionResult) -> ExtractionResult:
        # Only extracted table cells; never page headers, paths, images or summaries.
        tables: dict[int, str] = {}
        for row in raw.rows:
            if not any([row.date, row.debit, row.credit, row.amount]):
                continue
            value = {
                k: getattr(row, k)
                for k in ["date", "description", "debit", "credit", "amount", "balance"]
            }
            tables[row.page] = (
                tables.get(row.page, "") + json.dumps(value, ensure_ascii=False) + "\n"
            )
        if not tables:
            raise StmtconvError(
                "AI_TABLE_MISSING",
                "No safely isolated transaction cells are available; improve the profile or review manually.",
            )
        return extract(provider, gate(), raw, source_file, tables, [order.client_alias], consume)

    return run
