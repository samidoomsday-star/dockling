"""Date parsing never guesses an ambiguous numeric order or a missing year."""

import re
from datetime import date, datetime, timedelta
from typing import Literal

DateOrder = Literal["auto", "DMY", "MDY", "YMD"]


def clean_date(text: str) -> str:
    return re.sub(
        r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)(?:DAY|SDAY|NESDAY|RSDAY|URDAY)?\b[, ]*",
        "",
        text.upper(),
    ).strip()


def resolve_order(texts: list[str], order: DateOrder) -> tuple[DateOrder, list[str]]:
    if order != "auto":
        return order, []
    evidence: set[str] = set()
    ambiguous = False
    for text in texts:
        match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-]\d{2,4})?", clean_date(text))
        if match:
            first, second = int(match[1]), int(match[2])
            if first > 12 and second <= 12:
                evidence.add("DMY")
            elif second > 12 and first <= 12:
                evidence.add("MDY")
            else:
                ambiguous = True
    if len(evidence) == 1:
        return ("DMY" if "DMY" in evidence else "MDY"), []
    if len(evidence) > 1 or ambiguous:
        return "auto", ["DATE_ORDER_AMBIGUOUS"]
    return "YMD", []


def parse_date(
    text: str,
    order: DateOrder,
    period_start: date | None,
    period_end: date | None,
    formats: list[str] | None = None,
    allowance_days: int = 7,
) -> tuple[date | None, list[str]]:
    value = clean_date(text)
    flags: list[str] = []
    numeric = re.fullmatch(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?", value)
    if numeric and order == "auto":
        return None, ["DATE_ORDER_AMBIGUOUS"]
    base_formats = ["%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%d %b", "%b %d"]
    if order in {"DMY", "MDY"}:
        prefix = "%d/%m" if order == "DMY" else "%m/%d"
        base_formats = [
            prefix + "/%Y",
            prefix + "/%y",
            prefix,
            prefix.replace("/", "-") + "-%Y",
            prefix.replace("/", "-") + "-%y",
            *base_formats,
        ]
    chosen_formats = [*(formats or []), *base_formats]
    for pattern in dict.fromkeys(chosen_formats):
        if numeric and (
            (order == "DMY" and pattern.startswith("%m"))
            or (order == "MDY" and pattern.startswith("%d"))
        ):
            continue
        try:
            input_value, input_pattern = value, pattern
            if "%Y" not in pattern and "%y" not in pattern:
                # Leap-safe reference year parses month/day; the actual year is inferred below.
                input_value, input_pattern = value + " 2000", pattern + " %Y"
            parsed = datetime.strptime(input_value, input_pattern).date()
        except ValueError:
            continue
        if "%Y" not in pattern and "%y" not in pattern:
            if period_start is None or period_end is None:
                return None, ["YEAR_UNKNOWN"]
            year = period_start.year if parsed.month >= period_start.month else period_end.year
            try:
                parsed = parsed.replace(year=year)
            except ValueError:
                return None, ["DATE_UNPARSABLE"]
        if (
            period_start
            and period_end
            and not period_start - timedelta(days=allowance_days)
            <= parsed
            <= period_end + timedelta(days=allowance_days)
        ):
            flags.append("DATE_OUT_OF_PERIOD")
        return parsed, flags
    return None, ["DATE_UNPARSABLE"]
