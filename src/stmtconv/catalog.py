"""Validated configuration stubs; phase-specific business rules come later."""

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from stmtconv.config import read_yaml, validation_error


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PricePackage(Schema):
    name: str = Field(min_length=1)
    page_limit: int | None = Field(default=None, ge=1)
    price_min: Decimal = Field(ge=0)
    price_max: Decimal = Field(ge=0)

    @field_validator("price_min", "price_max", mode="before")
    @classmethod
    def no_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("prices must be quoted decimal strings")
        return value

    @model_validator(mode="after")
    def ordered_prices(self) -> Self:
        if self.price_max < self.price_min:
            raise ValueError("price_max must be at least price_min")
        return self


class Pricing(Schema):
    packages: list[PricePackage] = Field(min_length=1)
    addons: dict[str, Decimal]

    @model_validator(mode="after")
    def unique_packages(self) -> Self:
        if len({p.name for p in self.packages}) != len(self.packages):
            raise ValueError("package names must be unique")
        if any(v < 0 for v in self.addons.values()):
            raise ValueError("addon ratios must be nonnegative")
        return self


class CategoryRule(Schema):
    category: str = Field(min_length=1)
    match: list[str] = Field(min_length=1)
    direction: Literal["debit", "credit", "any"] = "any"


class Categories(Schema):
    rules: list[CategoryRule]


class ExportFormat(Schema):
    columns: list[str]
    date_formats: list[str] = Field(min_length=1)


class Exports(Schema):
    formats: dict[Literal["excel", "qb_csv3", "qb_csv4", "xero_csv", "csv", "ofx"], ExportFormat]

    @model_validator(mode="after")
    def required_formats(self) -> Self:
        if set(self.formats) != {"excel", "qb_csv3", "qb_csv4", "xero_csv", "csv", "ofx"}:
            raise ValueError("all six output format stubs are required")
        return self


class Catalog(Schema):
    pricing: Pricing
    categories: Categories
    exports: Exports


def load_catalog(directory: Path) -> Catalog:
    data: dict[str, Schema] = {}
    schemas: list[tuple[str, type[Schema]]] = [
        ("pricing", Pricing),
        ("categories", Categories),
        ("exports", Exports),
    ]
    for name, schema in schemas:
        try:
            data[name] = schema.model_validate(read_yaml(directory / f"{name}.yaml"))
        except ValidationError as exc:
            raise validation_error(f"{name}.yaml", exc) from exc
    return Catalog.model_validate(data)
