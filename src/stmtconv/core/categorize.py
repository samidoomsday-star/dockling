"""Pure ordered category rules; caller supplies validated rules as data."""

import re
from dataclasses import dataclass
from typing import Literal

from stmtconv.core.models import Statement


@dataclass(frozen=True)
class Rule:
    category: str
    match: list[str]
    direction: Literal["debit", "credit", "any"] = "any"


def categorize(statement: Statement, rules: list[Rule]) -> Statement:
    result = statement.model_copy(deep=True)
    for row in result.transactions:
        row.category = "Uncategorized"
        for rule in rules:
            if (
                rule.direction == "debit"
                and not row.debit
                or rule.direction == "credit"
                and not row.credit
            ):
                continue
            if any(
                re.search(pattern.removeprefix("regex:"), row.description, re.IGNORECASE)
                if pattern.startswith("regex:")
                else pattern.casefold() in row.description.casefold()
                for pattern in rule.match
            ):
                row.category = rule.category
                break
    return result
