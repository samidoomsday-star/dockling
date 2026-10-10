"""Explicit PostgreSQL configuration and versioned migrations; no runtime DDL."""

import ssl
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Protocol

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings


def database(config: HostedSettings) -> Engine:
    args: dict[str, object] = {"timeout": 5}
    if config.mode == "production":
        args["ssl_context"] = ssl.create_default_context()
    return create_engine(
        config.database_url.get_secret_value(),
        connect_args=args,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        hide_parameters=True,
    )


class UnitOfWork(Protocol):
    def transaction(self) -> AbstractContextManager[Session]: ...


class PostgresUnitOfWork:
    def __init__(self, engine: Engine):
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as db, db.begin():
            yield db


def migrate(config: HostedSettings) -> None:
    settings = Config()
    settings.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    engine = database(config)
    with engine.begin() as connection:
        settings.attributes["connection"] = connection
        command.upgrade(settings, "head")
        connection.exec_driver_sql(
            "GRANT SELECT ON alembic_version TO dockling_app, dockling_worker"
        )
    engine.dispose()
