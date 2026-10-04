"""Mask known names and identifiers in minimized table cells, never whole pages."""

import re

from stmtconv.logging_setup import redact_text


def table_text(text: str, names: list[str]) -> str:
    dates: dict[str, str] = {}

    def preserve_date(match: re.Match[str]) -> str:
        from datetime import date

        try:
            date.fromisoformat(match[0])
        except ValueError:
            return match[0]
        marker = f"[DATE{len(dates)}]"
        dates[marker] = match[0]
        return marker

    result = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", preserve_date, text)
    for name in sorted(set(names), key=len, reverse=True):
        if name.strip():
            result = re.sub(re.escape(name), "[NAME REDACTED]", result, flags=re.IGNORECASE)
    result = re.sub(r"(?<!\d)(?:\+?\d[\d ()-]{8,}\d)(?!\d)", "[IDENTIFIER REDACTED]", result)
    result = redact_text(result)
    for marker, value in dates.items():
        result = result.replace(marker, value)
    return result
