"""Bounded input commands; financial values are never browser floats."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["owner", "editor", "viewer"]
Output = Literal["excel", "csv", "qb_csv3", "qb_csv4", "xero_csv", "ofx"]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class JobOptions(Command):
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date_order: Literal["auto", "DMY", "MDY", "YMD"]
    output_date_format: Literal["ISO", "MM/DD/YYYY", "DD/MM/YYYY"] = "ISO"
    outputs: list[Output] = Field(min_length=1, max_length=6)
    merge: bool = False
    categorize: bool = False
    combine: bool = False
    engine: Literal["auto", "text", "docling"] = "auto"
    profile_id: str | None = Field(default=None, max_length=100)
    pages: str | None = Field(default=None, max_length=250)
    ai_selection: None = None  # hosted AI selections require Phase 4

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("A visible name is required")
        return value

    @field_validator("outputs")
    @classmethod
    def distinct(cls, value: list[Output]) -> list[Output]:
        if len(value) != len(set(value)):
            raise ValueError("Output formats must be distinct")
        return value

    @field_validator("profile_id")
    @classmethod
    def published_profile(cls, value: str | None) -> str | None:
        if value is not None:
            import re

            if not re.fullmatch(r"[a-z0-9_-]{1,80}", value):
                raise ValueError("Use a published profile identifier")
        return value

    @field_validator("pages")
    @classmethod
    def page_selection(cls, value: str | None) -> str | None:
        import re

        if value is not None and not re.fullmatch(
            r"[1-9][0-9]*(?:-[1-9][0-9]*)?(?:,[1-9][0-9]*(?:-[1-9][0-9]*)?)*", value
        ):
            raise ValueError("Use distinct page ranges")
        return value


class RevisionCommand(Command):
    expected_revision: int = Field(ge=1, le=9007199254740991)


class PipelineCommand(RevisionCommand):
    action: Literal["extract", "retry"]
    retry_operation_id: UUID | None = Field(default=None, strict=False)


class PasswordCommand(RevisionCommand):
    password: str = Field(min_length=1, max_length=512, repr=False)


class FileOrderCommand(RevisionCommand):
    file_ids: list[Annotated[UUID, Field(strict=False)]] = Field(min_length=1, max_length=30)


class WorkspaceSelect(Command):
    workspace_id: UUID = Field(strict=False)


class MemberCommand(Command):
    expected_version: int = Field(ge=1, le=9007199254740991)
    role: Role | None = None
    active: bool | None = None

    @field_validator("role", "active", mode="before")
    @classmethod
    def supplied_change(cls, value: object) -> object:
        if value is None:
            raise ValueError("A supplied membership change must have a value")
        return value

    @model_validator(mode="after")
    def change_required(self) -> Self:
        if self.role is None and self.active is None:
            raise ValueError("A membership change is required")
        return self


class InvitationCreate(Command):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: Literal["editor", "viewer"]


class InvitationAccept(Command):
    token: str = Field(min_length=1, max_length=512)
