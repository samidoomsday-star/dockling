"""Quotes use shared prices and measured anonymous timings when available."""

import json
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from stmtconv.catalog import Pricing
from stmtconv.config import Settings
from stmtconv.errors import StmtconvError
from stmtconv.orders.models import Order


@dataclass(frozen=True)
class Quote:
    package: str
    pages: int
    price_min: Decimal
    price_max: Decimal
    seconds: float
    addons: list[str]


def quote(order: Order, pricing: Pricing, settings: Settings) -> Quote:
    pages = sum(order.pages_by_kind.values())
    if pages == 0:
        raise StmtconvError("QUOTE_EMPTY", "Complete intake before requesting a quote.")
    eligible = sorted(
        (p for p in pricing.packages if p.page_limit is None or p.page_limit >= pages),
        key=lambda p: p.page_limit if p.page_limit is not None else 10**9,
    )
    if not eligible:
        raise StmtconvError("QUOTE_LIMIT", "No configured package covers this order.")
    package = eligible[0]
    addons = list(order.addons)
    if order.pages_by_kind.get("scanned", 0) and "scanned" not in addons:
        addons.append("scanned")
    if any(name not in pricing.addons for name in addons):
        raise StmtconvError("QUOTE_ADDON", "An add-on has no configured price.")
    factor = Decimal(1) + sum((pricing.addons[name] for name in set(addons)), Decimal(0))
    timings = dict(settings.default_seconds_per_page)
    ledger = settings.workspace / "ledger.jsonl"
    if ledger.is_file():
        samples: dict[str, list[float]] = {"text": [], "scanned": []}
        try:
            for line in ledger.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record.get("outcome", "delivered") != "delivered":
                    continue
                for kind in samples:
                    value = record.get("seconds_per_page", {}).get(kind)
                    if isinstance(value, (int, float)) and value > 0:
                        samples[kind].append(float(value))
        except (OSError, ValueError, AttributeError) as exc:
            raise StmtconvError("LEDGER_READ", "Anonymous timing ledger is invalid.") from exc
        for kind, values in samples.items():
            if len(values) >= 5:
                timings[kind] = median(values)
    seconds = sum(order.pages_by_kind.get(kind, 0) * value for kind, value in timings.items())
    return Quote(
        package.name,
        pages,
        (package.price_min * factor).quantize(Decimal("0.01")),
        (package.price_max * factor).quantize(Decimal("0.01")),
        seconds,
        addons,
    )
