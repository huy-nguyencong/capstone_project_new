"""Explicit, idempotent development reference-data seed."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping

import sqlalchemy as sa

from person_search.auth.passwords import PasswordHasher
from person_search.config import PostgresSettings

DEVELOPMENT_AREAS = (
    (uuid.UUID("10000000-0000-4000-8000-000000000001"), "CAMPUS", "Campus"),
    (uuid.UUID("10000000-0000-4000-8000-000000000002"), "GATE-A", "Gate A"),
)

DEVELOPMENT_PASSWORD = "password"
DEVELOPMENT_USERS = (
    (
        uuid.UUID("20000000-0000-4000-8000-000000000001"),
        "admin",
        "Admin",
        "ADMIN",
        None,
    ),
    (
        uuid.UUID("20000000-0000-4000-8000-000000000002"),
        "operator",
        "Operator",
        "OPERATOR",
        "GATE-A",
    ),
    (
        uuid.UUID("20000000-0000-4000-8000-000000000003"),
        "viewer",
        "Viewer",
        "VIEWER",
        None,
    ),
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


def seed_development_users(
    environment: Mapping[str, str] | None = None,
    *,
    hasher: PasswordHasher | None = None,
) -> int:
    """Create the three fixed local-demo accounts without overwriting existing users."""

    values = os.environ if environment is None else environment
    if values.get("PERSON_SEARCH_ENV", "development").strip().lower() == "production":
        raise RuntimeError("Development users cannot be seeded in production.")

    engine = sa.create_engine(PostgresSettings.from_environment(values).dsn)
    password_hasher = hasher or PasswordHasher()
    existing_statement = sa.text(
        "SELECT username FROM users WHERE username IN :usernames"
    ).bindparams(sa.bindparam("usernames", expanding=True))
    insert_statement = sa.text(
        "INSERT INTO users "
        "(id, username, password_hash, display_name, role, status, assigned_area_id) "
        "SELECT :id, :username, :password_hash, :display_name, :role, 'ACTIVE', area.id "
        "FROM (SELECT 1) seed "
        "LEFT JOIN areas area ON area.code = :area_code "
        "WHERE :area_code IS NULL OR area.id IS NOT NULL "
        "ON CONFLICT (username) DO NOTHING"
    )
    try:
        with engine.begin() as connection:
            usernames = tuple(row[1] for row in DEVELOPMENT_USERS)
            existing = set(connection.scalars(existing_statement, {"usernames": usernames}))
            inserted = 0
            for user_id, username, display_name, role, area_code in DEVELOPMENT_USERS:
                if username in existing:
                    continue
                result = connection.execute(
                    insert_statement,
                    {
                        "id": user_id,
                        "username": username,
                        "password_hash": password_hasher.hash(DEVELOPMENT_PASSWORD),
                        "display_name": display_name,
                        "role": role,
                        "area_code": area_code,
                    },
                )
                if result.rowcount != 1:
                    raise RuntimeError(f"Required development area is missing for '{username}'.")
                inserted += result.rowcount
            return inserted
    finally:
        engine.dispose()


def main() -> None:
    """Seed stable local-development areas and demo accounts."""

    areas_inserted = seed_reference_data()
    users_inserted = seed_development_users()
    print(
        "Development seed complete: "
        f"{areas_inserted} area row(s), {users_inserted} user row(s) inserted."
    )
