"""Owner-controlled workspace connections. Public projections never contain credentials."""

from collections.abc import Callable, Iterator
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.ai.providers import Model, Provider, choose
from stmtconv.config import HostedSettings
from stmtconv.errors import StmtconvError
from stmtconv.extract.ai_engine import Transport, discover
from stmtconv.web.egress import PublicTransport, endpoint
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import Connection, Event, now
from stmtconv.web.pipeline_api import Scope
from stmtconv.web.repository import Json, replay
from stmtconv.web.schemas import Command, RevisionCommand
from stmtconv.web.vault import Vault

EFFORT_ORDER = ["provider_default", "minimal", "low", "medium", "high", "xhigh", "max"]


class ConnectionCreate(Command):
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=8, max_length=300)
    requires_key: bool = True
    api_style: Literal["chat", "responses"] = "chat"
    effort_style: Literal["reasoning_effort", "reasoning", "none"] = "reasoning_effort"
    schema_style: Literal["json_schema", "json_object", "prompt_json"] = "prompt_json"
    token_field: Literal["max_tokens", "max_completion_tokens", "max_output_tokens"] = "max_tokens"
    models_route: str = Field(default="/models", max_length=100)
    completion_route: str = Field(default="/chat/completions", max_length=100)
    temperature_zero: bool = False

    @field_validator("name")
    @classmethod
    def visible(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Use a visible connection name")
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def public_endpoint(cls, value: str) -> str:
        try:
            endpoint(value)
        except StmtconvError as exc:
            raise ValueError("Public HTTPS endpoint required") from exc
        return value.rstrip("/")


class KeyCommand(RevisionCommand):
    api_key: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("api_key")
    @classmethod
    def plain_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not raw.strip() or any(ord(c) < 33 or ord(c) > 126 for c in raw):
            raise ValueError("Use the provider's plain API key")
        return value


class ManualModel(RevisionCommand):
    model_id: str = Field(min_length=1, max_length=200)

    @field_validator("model_id")
    @classmethod
    def visible_model(cls, value: str) -> str:
        if any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Use the exact model identifier")
        return value


class Selection(ManualModel):
    effort: Literal[
        "highest", "provider_default", "minimal", "low", "medium", "high", "xhigh", "max"
    ] = "highest"


class Terms(RevisionCommand):
    confirmed: bool
    terms_version: str = Field(min_length=8, max_length=200)

    @field_validator("terms_version")
    @classmethod
    def terms_reference(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use the provider terms URL without credentials/query data")
        return value


def public(connection: Connection) -> Json:
    return {
        "id": str(connection.id),
        "name": connection.name,
        "version": connection.version,
        "active": connection.active,
        "has_key": connection.ciphertext is not None,
        "base_url": connection.config["base_url"],
        "requires_key": connection.config.get("requires_key", True),
        "api_style": connection.config.get("api_style", "chat"),
        "effort_style": connection.config.get("effort_style", "reasoning_effort"),
        "models": connection.models,
        "selected_model": connection.selected_model,
        "effort": connection.effort,
        "terms_confirmed": connection.terms_version is not None,
        "terms_version": connection.terms_version,
        "tested_at": connection.tested_at.isoformat() if connection.tested_at else None,
        "test_code": connection.test_code,
    }


def get_connection(
    db: Session, workspace: UUID, identifier: UUID, *, active: bool = False
) -> Connection:
    record = db.scalar(
        select(Connection).where(Connection.workspace_id == workspace, Connection.id == identifier)
    )
    if record is None or active and not record.active:
        raise missing()
    return record


def provider(connection: Connection, vault: Vault) -> Provider:
    key = (
        vault.decrypt(connection.workspace_id, connection.id, connection.ciphertext)
        if connection.ciphertext
        else None
    )
    return Provider.model_validate(
        {
            "name": "hosted",
            **connection.config,
            "api_key": key,
            "models": connection.models,
            "selected_model": connection.selected_model,
            "effort": connection.effort,
            "terms_confirmed": connection.terms_version is not None,
        }
    )


def transport(provider: Provider) -> Transport:
    """Tests replace this factory with fake providers; production has no bypass flag."""
    return PublicTransport(provider)


def register_connections(
    app: FastAPI,
    config: HostedSettings,
    db_provider: Callable[[], Iterator[Session]],
    scoped: Scope,
    key: Callable[[Request], str],
) -> None:
    Db = Annotated[Session, Depends(db_provider, scope="function")]
    vault = Vault(config)

    @app.get("/api/v1/connections")
    def connections(request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        records = db.scalars(
            select(Connection)
            .where(Connection.workspace_id == ws)
            .order_by(Connection.id)
            .limit(100)
        )
        return {"items": [public(r) for r in records], "next_cursor": None}

    @app.get("/api/v1/connections/{identifier}")
    def connection(identifier: UUID, request: Request, db: Db) -> Json:
        ws, _ = scoped(db, request)
        return public(get_connection(db, ws, identifier))

    @app.post("/api/v1/connections", status_code=201)
    def create(command: ConnectionCreate, request: Request, db: Db) -> Json:
        ws, actor = scoped(db, request, write=True, owner=True)

        def run() -> Json:
            records = list(db.scalars(select(Connection.id).where(Connection.workspace_id == ws)))
            if len(records) >= 20:
                raise WebError(
                    429, "CONNECTION_LIMIT", "This workspace has reached its connection limit."
                )
            try:
                Provider.model_validate({"name": "hosted", **command.model_dump(exclude={"name"})})
            except ValueError:
                raise WebError(
                    422, "CONNECTION_CONFIG", "Check the compatible API routes and settings."
                ) from None
            record = Connection(
                id=uuid4(),
                workspace_id=ws,
                name=command.name,
                config=command.model_dump(exclude={"name"}),
            )
            db.add(record)
            db.flush()
            db.add(Event(workspace_id=ws, actor_id=actor.id, action="connection.created"))
            return public(record)

        return replay(
            db,
            ws,
            actor.id,
            "connection.create",
            key(request),
            command.model_dump(mode="json"),
            run,
        )

    def modify(
        identifier: UUID,
        command: RevisionCommand,
        request: Request,
        db: Session,
        action: str,
        run: Callable[[Connection], Json],
    ) -> Json:
        ws, actor = scoped(db, request, write=True, owner=True)
        record = get_connection(db, ws, identifier, active=action != "revoke")
        payload = command.model_dump(mode="json")
        if isinstance(command, KeyCommand):
            import hashlib
            import hmac

            payload["api_key"] = hmac.new(
                config.session_key.get_secret_value().encode(),
                (
                    str(ws) + ":" + str(identifier) + ":" + command.api_key.get_secret_value()
                ).encode(),
                hashlib.sha256,
            ).hexdigest()

        def execute() -> Json:
            if command.expected_revision != record.version:
                raise WebError(
                    409, "REVISION_CONFLICT", "The connection changed. Refresh before trying again."
                )
            result = run(record)
            db.add(
                Event(
                    workspace_id=ws,
                    actor_id=actor.id,
                    action="connection." + action,
                    revision=record.version,
                )
            )
            return result

        return replay(
            db,
            ws,
            actor.id,
            "connection." + action + ":" + str(identifier),
            key(request),
            payload,
            execute,
        )

    def changed(record: Connection) -> None:
        record.version += 1
        record.tested_at, record.test_code = None, None
        # Consent will bind this exact version in the next Phase 4 milestone.

    @app.put("/api/v1/connections/{identifier}/key")
    def replace_key(identifier: UUID, command: KeyCommand, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            record.ciphertext = vault.encrypt(
                record.workspace_id, record.id, command.api_key.get_secret_value()
            )
            changed(record)
            return public(record)

        return modify(identifier, command, request, db, "key.replaced", run)

    @app.post("/api/v1/connections/{identifier}/revoke")
    def revoke(identifier: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            record.active, record.ciphertext, record.terms_version = False, None, None
            changed(record)
            return public(record)

        return modify(identifier, command, request, db, "revoke", run)

    @app.post("/api/v1/connections/{identifier}/models")
    @app.post("/api/v1/connections/{identifier}/test")
    def models(identifier: UUID, command: RevisionCommand, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            selected = provider(record, vault)
            if selected.requires_key and selected.api_key is None:
                raise WebError(
                    409, "CONNECTION_KEY", "Add your API key before testing or discovering models."
                )
            try:
                discovered = discover(selected, transport(selected))
                if len(discovered) > 500:
                    raise StmtconvError(
                        "AI_MODELS_SCHEMA", "The provider returned too many models."
                    )
            except StmtconvError as exc:
                # Failed requests don't alter the current working catalog/selection.
                raise WebError(502, exc.code, exc.message) from None
            manual = [Model.model_validate(m) for m in record.models if m.get("manual")]
            merged = {m.id: m for m in [*manual, *discovered]}
            record.models = [m.model_dump(mode="json") for m in merged.values()]
            test_code = "MODELS_CONFIRMED"
            if record.selected_model and record.selected_model not in merged:
                test_code = "AI_MODEL_UNAVAILABLE"
            elif (
                record.selected_model and record.effort not in merged[record.selected_model].efforts
            ):
                test_code = "AI_EFFORT_UNSUPPORTED"
            changed(record)
            record.tested_at, record.test_code = now(), test_code
            return public(record)

        return modify(identifier, command, request, db, "models", run)

    @app.post("/api/v1/connections/{identifier}/models/manual")
    def manual(identifier: UUID, command: ManualModel, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            if not any(m["id"] == command.model_id for m in record.models):
                record.models = [
                    *record.models,
                    Model(id=command.model_id, manual=True).model_dump(mode="json"),
                ]
                if len(record.models) > 500:
                    raise WebError(
                        429,
                        "MODEL_LIMIT",
                        "Remove a connection or use discovery within the model limit.",
                    )
                changed(record)
            return public(record)

        return modify(identifier, command, request, db, "model.manual", run)

    @app.post("/api/v1/connections/{identifier}/selection")
    def selection(identifier: UUID, command: Selection, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            current = Provider.model_validate(
                {"name": "hosted", **record.config, "models": record.models}
            )
            model = next((m for m in current.models if m.id == command.model_id), None)
            if model is None:
                raise WebError(
                    422,
                    "AI_MODEL_UNKNOWN",
                    "Discover models or add the exact model identifier manually.",
                )
            supported = [
                e
                for e in model.efforts
                if e == "provider_default" or current.effort_style != "none"
            ]
            effort = (
                max(supported, key=EFFORT_ORDER.index)
                if command.effort == "highest"
                else command.effort
            )
            try:
                selected = choose(current, command.model_id, effort)
            except StmtconvError as exc:
                raise WebError(422, exc.code, exc.message) from None
            record.selected_model, record.effort = selected.selected_model, selected.effort
            changed(record)
            return public(record)

        return modify(identifier, command, request, db, "selection", run)

    @app.post("/api/v1/connections/{identifier}/terms")
    def terms(identifier: UUID, command: Terms, request: Request, db: Db) -> Json:
        def run(record: Connection) -> Json:
            record.terms_version = command.terms_version if command.confirmed else None
            changed(record)
            return public(record)

        return modify(identifier, command, request, db, "terms", run)
