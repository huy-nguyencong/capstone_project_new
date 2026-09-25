"""Explicit, idempotent development reference-data seed."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping

import sqlalchemy as sa

from person_search.config import PostgresSettings

DEVELOPMENT_AREAS = (
    (uuid.UUID("10000000-0000-4000-8000-000000000001"), "CAMPUS", "Campus"),
    (uuid.UUID("10000000-0000-4000-8000-000000000002"), "GATE-A", "Gate A"),
)


def seed_reference_data(environment: Mapping[str, str] | None = None) -> int:
    """Insert non-secret reference rows and return the number newly inserted."""

    values = os.environ if environment is None else environment
    engine = sa.create_engine(PostgresSettings.from_environment(values).dsn)
    statement = sa.text(
        "INSERT INTO areas (id, code, name) VALUES (:id, :code, :name) "
        "ON CONFLICT (code) DO NOTHING"
    )
    try:
        with engine.begin() as connection:
            return sum(
                connection.execute(
                    statement, {"id": row[0], "code": row[1], "name": row[2]}
                ).rowcount
                for row in DEVELOPMENT_AREAS
            )
    finally:
        engine.dispose()


def main() -> None:
    """CLI entry point. It intentionally never creates users or credentials."""

    inserted = seed_reference_data()
    print(f"Reference seed complete: {inserted} area row(s) inserted.")
