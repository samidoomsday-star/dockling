"""Typed engine contract; normalization and validation stay outside engines."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from stmtconv.core.models import RawRow, StatementSummary
from stmtconv.profiles.schema import Profile


@dataclass(frozen=True)
class PageSet:
    path: Path
    source_file: str
    pages: list[int]
    scanned: bool = False
    summary_pages: list[int] = field(default_factory=list)


@dataclass
class ExtractionResult:
    rows: list[RawRow]
    summary: StatementSummary
    flags: list[str] = field(default_factory=list)
    diagnostics: dict[str, dict[str, object]] = field(default_factory=dict)
    summary_pages: list[int] = field(default_factory=list)


class Extractor(Protocol):
    def extract(self, pages: PageSet, profile: Profile) -> ExtractionResult: ...
