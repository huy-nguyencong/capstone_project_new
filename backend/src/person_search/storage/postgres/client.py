"""PostgreSQL engine and session factory."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from person_search.config import PostgresSettings


class PostgresStorage:
    name = "postgres"

    def __init__(self, engine: Engine, session_factory: sessionmaker[Session]) -> None:
        self.engine = engine
        self.session_factory = session_factory

    @classmethod
    def from_settings(
        cls,
        settings: PostgresSettings,
        *,
        engine_factory: Callable[..., Engine] = create_engine,
    ) -> PostgresStorage:
        engine = engine_factory(
            settings.dsn,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout_seconds,
            pool_pre_ping=True,
            connect_args={"connect_timeout": settings.connect_timeout_seconds},
        )
        return cls(engine, sessionmaker(bind=engine, expire_on_commit=False))

    def check_health(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        self.engine.dispose()
