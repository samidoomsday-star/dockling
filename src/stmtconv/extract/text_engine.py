"""Word geometry and profile data, with no bank-specific branches."""

import hashlib
import re
from dataclasses import dataclass
from time import perf_counter

import pdfplumber

from stmtconv.core.dates import parse_date
from stmtconv.core.models import RawRow, StatementSummary
from stmtconv.core.money import parse_money
from stmtconv.extract.base import ExtractionResult, PageSet
from stmtconv.profiles.schema import Profile


@dataclass(frozen=True)
class Word:
    text: str
    x: float
    right: float
    y: float


def lines(words: list[Word], tolerance: float) -> list[list[Word]]:
    result: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.y, w.x)):
        if not result or abs(word.y - result[-1][0].y) > tolerance:
            result.append([word])
        else:
            result[-1].append(word)
    return [sorted(line, key=lambda w: w.x) for line in result]


def header(line: list[Word], profile: Profile) -> dict[str, float]:
    positions: dict[str, float] = {}
    for field, aliases in profile.header_aliases.items():
        for word in line:
            if word.text.lower().strip(":") in {a.lower() for a in aliases}:
                positions[field] = word.x
    return (
        positions
        if {"date", "description"} <= set(positions)
        and set(positions) & {"amount", "debit", "credit"}
        else {}
    )


def summary_from_text(text: str, profile: Profile) -> tuple[StatementSummary, list[str]]:
    summary = StatementSummary(direction=profile.direction)
    flags = []
    for key, pattern in profile.summary_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        try:
            if key in {"opening", "closing", "total_debits", "total_credits"}:
                parsed = parse_money(value, profile.decimal_separator, profile.thousands_separator)
                setattr(summary, key, parsed)
            elif key in {"period_start", "period_end"}:
                parsed_date, issues = parse_date(
                    value, profile.date_order, None, None, profile.date_formats
                )
                setattr(summary, key, parsed_date)
                flags.extend(issues)
            elif key == "account_mask":
                identifier = re.sub(r"\W", "", value)
                summary.account_mask = "****" + identifier[-4:]
                if identifier.isdigit() and len(identifier) >= 8:
                    summary.account_key = hashlib.sha256(identifier.encode()).hexdigest()
            elif key == "currency":
                summary.currency = value.upper()
        except ValueError:
            flags.append("SUMMARY_UNPARSABLE")
    return summary, flags


class TextExtractor:
    def extract(self, pages: PageSet, profile: Profile) -> ExtractionResult:
        rows: list[RawRow] = []
        diagnostics: dict[str, dict[str, object]] = {}
        page_texts = []
        with pdfplumber.open(pages.path) as document:
            for number in pages.pages:
                page_started = perf_counter()
                page = document.pages[number - 1]
                text = page.extract_text() or ""
                page_texts.append(text)
                words = [
                    Word(str(w["text"]), float(w["x0"]), float(w["x1"]), float(w["top"]))
                    for w in page.extract_words()
                ]
                active: dict[str, float] = {}
                page_rows = 0
                for line in lines(words, profile.line_tolerance):
                    content = " ".join(w.text for w in line)
                    detected = header(line, profile)
                    if detected:
                        active = detected
                        continue
                    if not active or any(
                        re.search(pattern, content, re.IGNORECASE)
                        for pattern in profile.noise_patterns
                    ):
                        continue
                    cells: dict[str, list[str]] = {key: [] for key in active}
                    positions = sorted(active.items(), key=lambda item: item[1])
                    for word in line:
                        center = (word.x + word.right) / 2
                        if profile.columns:
                            key = next(
                                (k for k, (a, b) in profile.columns.items() if a <= center < b),
                                None,
                            )
                        else:
                            key = positions[0][0]
                            for (_left_key, left), (right_key, right) in zip(
                                positions, positions[1:], strict=False
                            ):
                                if center >= (left + right) / 2:
                                    key = right_key
                        if key in cells:
                            cells[key].append(word.text)
                    values = {key: " ".join(parts) for key, parts in cells.items()}
                    rows.append(
                        RawRow(
                            **values,
                            page=number,
                            source_file=pages.source_file,
                            engine="text",
                            raw_text=content,
                        )
                    )
                    if values.get("date") or any(
                        values.get(k) for k in ["amount", "debit", "credit"]
                    ):
                        page_rows += 1
                diagnostics[str(number)] = {
                    "engine": "text",
                    "rows": page_rows,
                    "header_found": bool(active),
                    "seconds": perf_counter() - page_started,
                }
        summary, flags = summary_from_text("\n".join(page_texts), profile)
        return ExtractionResult(rows, summary, flags, diagnostics)
