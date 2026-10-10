"""Validated non-secret configuration versions, captured for future jobs only."""

from decimal import Decimal
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.catalog import Exports, Pricing, load_catalog
from stmtconv.config import Settings, resolve_config_dir
from stmtconv.profiles.schema import Profile, load_profiles
from stmtconv.web.errors import WebError
from stmtconv.web.models import ConfigHead, ConfigVersion


class Processing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    balance_tolerance: Decimal = Field(default=Decimal("0.01"), ge=0, le=Decimal("0.01"))
    date_out_of_period_days: int = Field(default=7, ge=0, le=7)
    qb_csv_max_rows: int = Field(default=1000, ge=1, le=1000)

    @field_validator("balance_tolerance", mode="before")
    @classmethod
    def exact(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("Use exact decimal text")
        return value


class Templates(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    delivery_note: str = Field(min_length=1, max_length=4000)


def baseline(section: str) -> dict[str, object]:
    if section == "processing":
        return Processing().model_dump(mode="json")
    if section == "templates":
        return {
            "delivery_note": "These files are ready for your source review and accounting import checks."
        }
    catalog = load_catalog(resolve_config_dir())
    if section in {"pricing", "exports"}:
        return cast(dict[str, object], getattr(catalog, section).model_dump(mode="json"))
    if section.startswith("profile_"):
        identifier = section.removeprefix("profile_")
        profiles = load_profiles()
        profile = next((p for p in profiles if p.id == identifier), None)
        if profile is None:
            profile = next(p for p in profiles if p.id == "generic").model_copy(
                update={"id": identifier, "display_name": identifier, "fingerprints": []}
            )
        return profile.model_dump(mode="json")
    raise WebError(404, "NOT_FOUND", "This configuration section is unavailable.")


def validate(section: str, data: dict[str, object]) -> dict[str, object]:
    import json
    import re

    if len(json.dumps(data).encode()) > 32000:
        raise ValueError("Configuration limit")
    if section.startswith("profile_"):
        profile = Profile.model_validate(data)
        if (
            profile.id != section.removeprefix("profile_")
            or len(profile.id) > 80
            or len(profile.display_name) > 120
        ):
            raise ValueError("Profile identifier mismatch")
        patterns = [
            *profile.fingerprints,
            *profile.noise_patterns,
            *profile.summary_patterns.values(),
        ]
        if len(patterns) > 50 or any(len(p) > 500 for p in patterns):
            raise ValueError("Profile pattern limit")
        if any(len(v) > 100 for values in profile.header_aliases.values() for v in values):
            raise ValueError("Profile alias limit")
        return profile.model_dump(mode="json")
    if not re.fullmatch("[a-z_]{1,40}", section):
        raise ValueError("Section limit")
    models: dict[str, type[BaseModel]] = {
        "processing": Processing,
        "pricing": Pricing,
        "exports": Exports,
        "templates": Templates,
    }
    model = models.get(section)
    if model is None:
        raise ValueError("Unknown section")
    validated = model.model_validate(data)
    if section == "pricing":
        addons = data.get("addons", {})
        if isinstance(addons, dict) and any(isinstance(v, float) for v in addons.values()):
            raise ValueError("Use exact decimal text for addon ratios")
    if isinstance(validated, Exports):
        original = load_catalog(resolve_config_dir()).exports
        if any(
            validated.formats[k].columns != original.formats[k].columns
            or not set(v.date_formats).issubset(original.formats[k].date_formats)
            or not v.date_formats
            for k, v in validated.formats.items()
        ):
            raise ValueError("Preserve supported writer columns and date formats")
    return validated.model_dump(mode="json")


def active(db: Session, section: str) -> dict[str, object]:
    head = db.get(ConfigHead, section)
    if head and head.active_version is not None:
        revision = db.scalar(
            select(ConfigVersion).where(
                ConfigVersion.section == section, ConfigVersion.version == head.active_version
            )
        )
        assert revision is not None
        return revision.data
    return baseline(section)


def runtime_snapshot(db: Session) -> dict[str, object]:
    profiles = {p.id: p.model_dump(mode="json") for p in load_profiles()}
    for head in db.scalars(
        select(ConfigHead).where(
            ConfigHead.section.startswith("profile_"), ConfigHead.active_version.is_not(None)
        )
    ):
        profiles[head.section.removeprefix("profile_")] = active(db, head.section)
    if len(profiles) > 50:
        raise WebError(429, "PROFILE_LIMIT", "The active profile catalog is full.")
    return {
        "processing": active(db, "processing"),
        "exports": active(db, "exports"),
        "templates": active(db, "templates"),
        "profiles": list(profiles.values()),
    }


def processing_settings(runtime: dict[str, object]) -> Settings:
    from stmtconv.config import load_settings

    settings = load_settings()
    policy = Processing.model_validate(
        runtime.get("processing", Processing().model_dump(mode="json"))
    )
    return settings.model_copy(
        update={
            "balance_tolerance": policy.balance_tolerance,
            "date_out_of_period_days": policy.date_out_of_period_days,
            "qb_csv_max_rows": policy.qb_csv_max_rows,
        }
    )
