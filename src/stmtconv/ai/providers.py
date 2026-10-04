"""Private local BYOK settings; no environment access or network in this module."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)

from stmtconv.errors import StmtconvError
from stmtconv.orders.store import atomic_text

Effort = Literal["provider_default", "minimal", "low", "medium", "high", "xhigh", "max"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=200)
    efforts: list[Effort] = Field(default=["provider_default"], min_length=1)
    manual: bool = False
    capability_source: Literal["unknown", "provider_metadata", "operator_documentation"] = "unknown"
    capability_reference: str | None = None

    @model_validator(mode="after")
    def documented_capabilities(self) -> "Model":
        if self.capability_source == "unknown" and any(
            e != "provider_default" for e in self.efforts
        ):
            raise ValueError("non-default efforts require documented model capabilities")
        if self.capability_source == "operator_documentation" and not self.capability_reference:
            raise ValueError("documented capabilities require a reference")
        return self


class Provider(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    base_url: str
    api_key: SecretStr | None = None
    requires_key: bool = True
    terms_confirmed: bool = False
    api_style: Literal["chat", "responses"] = "chat"
    models_route: str = "/models"
    completion_route: str = "/chat/completions"
    effort_style: Literal["reasoning_effort", "reasoning", "none"] = "reasoning_effort"
    schema_style: Literal["json_schema", "json_object", "prompt_json"] = "prompt_json"
    token_field: Literal["max_tokens", "max_completion_tokens", "max_output_tokens"] = "max_tokens"
    temperature_zero: bool = False
    models: list[Model] = Field(default_factory=list)
    selected_model: str | None = None
    effort: Effort = "provider_default"

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("endpoint cannot contain credentials, query or fragment")
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("HTTPS required except explicit local loopback")
        return value.rstrip("/")

    @field_validator("models_route", "completion_route")
    @classmethod
    def valid_route(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"/[A-Za-z0-9_/-]+", value):
            raise ValueError("use a relative API route")
        return value

    @model_validator(mode="after")
    def compatible_effort(self) -> "Provider":
        if self.effort_style == "none" and self.effort != "provider_default":
            raise ValueError("effort is unsupported by this adapter")
        return self


class Providers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected: str | None = None
    providers: list[Provider] = Field(default_factory=list)


def path(workspace: Path) -> Path:
    directory = workspace / ".ai"
    file = directory / "providers.json"
    if directory.is_symlink() or file.is_symlink():
        raise StmtconvError("AI_SETTINGS_PATH", "AI settings cannot use a symbolic link.")
    return file


def load(workspace: Path) -> Providers:
    file = path(workspace)
    if not file.exists():
        return Providers()
    try:
        return Providers.model_validate_json(file.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise StmtconvError(
            "AI_SETTINGS_INVALID", "Private provider settings are invalid. Values are hidden."
        ) from exc


def save(workspace: Path, providers: Providers) -> None:
    import json

    providers = Providers.model_validate(providers.model_dump())
    value = providers.model_dump(mode="json")
    for item, provider in zip(value["providers"], providers.providers, strict=True):
        item["api_key"] = provider.api_key.get_secret_value() if provider.api_key else None
    file = path(workspace)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.parent.chmod(0o700)
    atomic_text(file, json.dumps(value, indent=2) + "\n")
    file.chmod(0o600)


def get(workspace: Path, name: str | None = None) -> Provider:
    settings = load(workspace)
    selected = name or settings.selected
    provider = next((p for p in settings.providers if p.name == selected), None)
    if provider is None:
        raise StmtconvError("AI_PROVIDER_MISSING", "Run ai setup and select a provider first.")
    return provider


def update(workspace: Path, provider: Provider, select: bool = False) -> None:
    settings = load(workspace)
    settings.providers = [p for p in settings.providers if p.name != provider.name] + [provider]
    if select:
        settings.selected = provider.name
    save(workspace, settings)


def choose(provider: Provider, model_id: str, effort: Effort, manual: bool = False) -> Provider:
    result = provider.model_copy(deep=True)
    model = next((m for m in result.models if m.id == model_id), None)
    if model is None and manual:
        model = Model(id=model_id, manual=True)
        result.models.append(model)
    if model is None:
        raise StmtconvError("AI_MODEL_UNKNOWN", "Discover models or use explicit manual entry.")
    if effort not in model.efforts or (
        effort != "provider_default" and provider.effort_style == "none"
    ):
        raise StmtconvError(
            "AI_EFFORT_UNSUPPORTED",
            "This model does not advertise the requested effort.",
            "Choose an advertised effort or provider default; nothing was changed.",
        )
    result.selected_model = model_id
    result.effort = effort
    return result
