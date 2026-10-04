"""Layout data is validated separately from extraction code."""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from stmtconv.config import read_yaml, validation_error
from stmtconv.errors import StmtconvError


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    display_name: str
    fingerprints: list[str] = Field(default_factory=list)
    direction: Literal["asset", "liability"] = "asset"
    header_aliases: dict[str, list[str]]
    amount_style: Literal["separate_columns", "signed_single", "dr_cr_suffix"] = "separate_columns"
    decimal_separator: str = "."
    thousands_separator: str = ","
    negative_patterns: list[str] = Field(default_factory=list)
    date_formats: list[str] = Field(default_factory=list)
    date_order: Literal["auto", "DMY", "MDY", "YMD"] = "auto"
    year_source: Literal["in_date", "period"] = "period"
    summary_patterns: dict[str, str] = Field(default_factory=dict)
    noise_patterns: list[str] = Field(default_factory=list)
    row_order: Literal["chronological", "reverse", "auto"] = "auto"
    columns: dict[str, tuple[float, float]] = Field(default_factory=dict)
    line_tolerance: float = Field(default=3, gt=0, le=20)

    @model_validator(mode="after")
    def valid_patterns(self) -> "Profile":
        if not {"date", "description"} <= set(self.header_aliases):
            raise ValueError("date and description aliases required")
        if set(self.header_aliases) - {
            "date",
            "description",
            "debit",
            "credit",
            "amount",
            "balance",
        }:
            raise ValueError("unknown column key")
        if (
            self.decimal_separator not in {".", ","}
            or self.decimal_separator == self.thousands_separator
        ):
            raise ValueError("invalid separators")
        for pattern in [*self.fingerprints, *self.noise_patterns, *self.summary_patterns.values()]:
            re.compile(pattern)
        if any(a >= b for a, b in self.columns.values()):
            raise ValueError("invalid column bounds")
        return self


def directory() -> Path:
    bundled = Path(__file__).resolve().parents[1] / "_profiles"
    local = Path.cwd() / "profiles"
    if (local / "generic.yaml").exists():
        return local
    return bundled if bundled.exists() else Path(__file__).resolve().parents[3] / "profiles"


def load_profiles(folder: Path | None = None) -> list[Profile]:
    result = []
    for path in sorted((folder or directory()).glob("*.yaml")):
        try:
            result.append(Profile.model_validate(read_yaml(path)))
        except (ValidationError, re.error) as exc:
            if isinstance(exc, ValidationError):
                raise validation_error(path.name, exc) from exc
            raise StmtconvError("PROFILE_INVALID", "Invalid profile expression.") from exc
    if not any(p.id == "generic" for p in result):
        raise StmtconvError("PROFILE_MISSING", "The generic profile is missing.")
    return result


def detect(text: str, profiles: list[Profile], requested: str | None = None) -> Profile:
    if requested:
        matching = [p for p in profiles if p.id == requested]
        if not matching:
            raise StmtconvError("PROFILE_UNKNOWN", "Unknown profile ID.")
        return matching[0]
    return next(
        (
            p
            for p in profiles
            if p.id != "generic"
            and p.fingerprints
            and all(re.search(f, text, re.IGNORECASE) for f in p.fingerprints)
        ),
        next(p for p in profiles if p.id == "generic"),
    )
