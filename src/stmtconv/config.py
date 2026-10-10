"""The sole process-environment reader; config errors never echo input values."""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from stmtconv.errors import ConfigurationError

YAML_VALUES: ContextVar[dict[str, object] | None] = ContextVar("yaml_settings", default=None)


class YamlValuesSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings], values: dict[str, object]) -> None:
        super().__init__(settings_cls)
        self.values = dict(values)
        if "artifacts_path" in self.values:
            self.values["DOCLING_ARTIFACTS_PATH"] = self.values.pop("artifacts_path")

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[object, str, bool]:
        return self.values.get(field_name), field_name, False

    def __call__(self) -> dict[str, object]:
        return self.values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STMTCONV_", extra="forbid", env_ignore_empty=True, populate_by_name=True
    )
    workspace: Path = Path("workspace")
    artifacts_path: Path = Field(
        default=Path("models"),
        validation_alias=AliasChoices("DOCLING_ARTIFACTS_PATH", "artifacts_path"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    num_threads: int = Field(default=4, ge=1, le=32)
    offline: bool = True
    balance_tolerance: Decimal = Field(default=Decimal("0.01"), ge=0)
    fallback_mismatch_ratio: float = Field(default=0.05, ge=0, le=1)
    min_rows: int = Field(default=1, ge=1)
    spot_check_rows: int = Field(default=10, ge=1)
    qb_csv_max_rows: int = Field(default=1000, ge=1)
    retention_days_after_delivery: int = Field(default=7, ge=0)
    ai_max_pages_per_order: int = Field(default=20, ge=1)
    max_file_mb: int = Field(default=100, ge=1)
    max_pages_per_order: int = Field(default=500, ge=1)
    date_out_of_period_days: int = Field(default=7, ge=0)
    default_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    output_date_format: str = "%m/%d/%Y"
    default_seconds_per_page: dict[str, float] = Field(
        default_factory=lambda: {"text": 0.5, "scanned": 15.0}
    )
    invoice_markers: list[str] = Field(default_factory=list)
    statement_markers: list[str] = Field(default_factory=list)
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_effort: str = "provider_default"
    ai_api_key: SecretStr | None = None
    ai_terms_confirmed: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            dotenv_settings,
            YamlValuesSource(settings_cls, YAML_VALUES.get() or {}),
            init_settings,
        )

    @field_validator("invoice_markers", "statement_markers")
    @classmethod
    def valid_document_patterns(cls, value: list[str]) -> list[str]:
        import re

        try:
            for pattern in value:
                re.compile(pattern)
        except re.error as exc:
            raise ValueError("invalid document marker") from exc
        return value

    @field_validator("balance_tolerance", mode="before")
    @classmethod
    def no_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("use a quoted decimal string for monetary settings")
        return value

    @field_validator("default_seconds_per_page")
    @classmethod
    def positive_timings(cls, value: dict[str, float]) -> dict[str, float]:
        if set(value) != {"text", "scanned"} or any(v <= 0 for v in value.values()):
            raise ValueError("positive text and scanned timings required")
        return value


def default_config_dir() -> Path:
    bundled = Path(__file__).parent / "_defaults"
    return bundled if bundled.is_dir() else Path(__file__).resolve().parents[2] / "config"


def resolve_config_dir(config_dir: Path | None = None) -> Path:
    if config_dir is not None:
        return config_dir.resolve()
    local = Path.cwd() / "config"
    return local if (local / "settings.yaml").is_file() else default_config_dir()


def read_yaml(path: Path) -> dict[str, object]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(
            "CONFIG_READ", f"Could not read {path.name}.", "Check the file and its YAML syntax."
        ) from exc
    if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
        raise ConfigurationError("CONFIG_FORMAT", f"{path.name} must contain a YAML mapping.")
    return dict(data)


def validation_error(filename: str, exc: ValidationError) -> ConfigurationError:
    fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
    return ConfigurationError(
        "CONFIG_INVALID",
        f"Invalid {filename}: {fields}.",
        "Check the named fields; input values are hidden.",
    )


def configure_offline(offline: bool) -> None:
    for name in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"]:
        os.environ[name] = "1" if offline else "0"
    constants = sys.modules.get("huggingface_hub.constants")
    if constants is not None:
        # huggingface_hub caches this flag at import time.
        constants.__dict__["HF_HUB_OFFLINE"] = offline


def load_settings(config_dir: Path | None = None, env_file: Path | None = None) -> Settings:
    directory = resolve_config_dir(config_dir)
    values = read_yaml(directory / "settings.yaml")
    token = YAML_VALUES.set(values)
    try:
        settings = Settings(_env_file=env_file or Path.cwd() / ".env")
    except ValidationError as exc:
        raise validation_error("settings.yaml / environment", exc) from exc
    finally:
        YAML_VALUES.reset(token)
    settings.workspace = settings.workspace.expanduser().resolve()
    settings.artifacts_path = settings.artifacts_path.expanduser().resolve()
    configure_offline(settings.offline)
    return settings


@contextmanager
def model_download_environment(cache_dir: Path | None = None) -> Iterator[None]:
    """Explicit setup-only network exception, restoring prior flags on failure too."""
    previous = {name: os.environ.get(name) for name in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"]}
    constants = sys.modules.get("huggingface_hub.constants")
    old_cached = getattr(constants, "HF_HUB_OFFLINE", None)
    cache_values = (
        {}
        if cache_dir is None
        else {
            "HF_HUB_CACHE": str(cache_dir / "hub"),
            "HF_XET_CACHE": str(cache_dir / "xet"),
        }
    )
    previous_cache = {name: os.environ.get(name) for name in cache_values}
    cached_values = {name: getattr(constants, name, None) for name in cache_values}
    for cache_path in cache_values.values():
        Path(cache_path).mkdir(parents=True, exist_ok=True)
    for cache_name, cache_value in cache_values.items():
        os.environ[cache_name] = cache_value
        if constants is not None:
            constants.__dict__[cache_name] = cache_value
    configure_offline(False)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        constants = sys.modules.get("huggingface_hub.constants")
        for name, value in previous_cache.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
            if constants is not None and cached_values[name] is not None:
                constants.__dict__[name] = cached_values[name]
        if constants is not None:
            constants.__dict__["HF_HUB_OFFLINE"] = (
                old_cached if old_cached is not None else previous["HF_HUB_OFFLINE"] == "1"
            )


class HostedSettings(BaseSettings):
    """Optional web configuration; the CLI still uses Settings above."""

    model_config = SettingsConfigDict(
        env_prefix="STMTCONV_WEB_", extra="ignore", env_ignore_empty=True
    )
    mode: Literal["local", "production"] = "local"
    database_url: SecretStr
    session_key: SecretStr
    base_url: str = "http://127.0.0.1:8000"
    oidc_issuer: str
    oidc_client_id: str = "dockling-web"
    oidc_client_secret: SecretStr = Field(min_length=16)
    admin_subjects: list[str] = Field(default_factory=list)
    mfa_amr: list[str] = Field(default=["otp", "mfa", "hwk"], min_length=1)
    s3_endpoint: str
    s3_access_key: SecretStr = Field(min_length=8)
    s3_secret_key: SecretStr = Field(min_length=16)
    s3_bucket: str = "dockling-private"
    session_hours: int = Field(default=8, ge=1, le=24)
    frontend_dist: Path = Path("frontend/dist")

    @model_validator(mode="after")
    def secure_boundaries(self) -> Self:
        from urllib.parse import urlsplit

        if not self.database_url.get_secret_value().startswith("postgresql+pg8000://"):
            raise ValueError("The web application requires PostgreSQL with the selected driver")
        if len(self.session_key.get_secret_value()) < 32:
            raise ValueError("A generated session signing key is required")
        for value in [self.base_url, self.oidc_issuer, self.s3_endpoint]:
            parsed = urlsplit(value)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Service URLs must not embed credentials or query data")
            if self.mode == "production" and parsed.scheme != "https":
                raise ValueError("Production services require HTTPS")
            if self.mode == "local" and (
                parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            ):
                raise ValueError("Local test services must use a loopback origin")
        if urlsplit(self.base_url).path not in {"", "/"}:
            raise ValueError("The application origin must not include a path")
        self.base_url = self.base_url.rstrip("/")
        self.oidc_issuer = self.oidc_issuer.rstrip("/")
        return self


def load_hosted_settings(path: Path = Path(".local-saas/server.env")) -> HostedSettings:
    try:
        return HostedSettings(_env_file=path)
    except ValidationError:
        raise ConfigurationError(
            "WEB_CONFIG", "Web settings are missing or invalid; no credential values are shown."
        ) from None
