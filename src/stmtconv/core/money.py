"""Strict financial token parsing, with explicit locale and suffix semantics."""

import re
from decimal import Decimal, InvalidOperation
from typing import Literal


def parse_money(
    text: str,
    decimal_separator: str = ".",
    thousands_separator: str = ",",
    suffix_negative: Literal["DR", "CR"] = "DR",
    exponent: int = 2,
) -> Decimal | None:
    if not text.strip():
        return None
    value = text.strip().replace("\u00a0", " ")
    value = re.sub(r"(?:USD|GBP|EUR|CAD|AUD|JPY|[$€£¥])", "", value, flags=re.IGNORECASE).strip()
    negative = False
    suffix = re.search(r"\s*(DR|CR)$", value, flags=re.IGNORECASE)
    if suffix:
        negative = suffix[1].upper() == suffix_negative
        value = value[: suffix.start()].strip()
    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]
    if value.startswith("-") or value.endswith("-"):
        negative = True
        value = value.removeprefix("-").removesuffix("-")
    value = value.removeprefix("+").strip()
    # Validate grouping; do not silently convert malformed 12,34 into 1234.
    integer, separator, fraction = value.partition(decimal_separator)
    if separator and (not fraction.isdigit() or len(fraction) > exponent):
        raise ValueError("Invalid monetary fractional digits")
    if thousands_separator and thousands_separator in integer:
        groups = integer.split(thousands_separator)
        if not 1 <= len(groups[0]) <= 3 or any(len(g) != 3 or not g.isdigit() for g in groups[1:]):
            raise ValueError("Invalid monetary grouping")
        integer = "".join(groups)
    integer = integer.replace(" ", "")
    if not integer.isdigit():
        raise ValueError("Invalid monetary token")
    normalized = integer + ("." + fraction if separator else "")
    try:
        parsed = Decimal(normalized).quantize(Decimal(1).scaleb(-exponent))
    except InvalidOperation as exc:
        raise ValueError("Invalid monetary value") from exc
    return -parsed if negative else parsed
