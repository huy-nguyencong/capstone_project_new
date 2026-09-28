"""Keep writing test suites away from the demo database (see ``pytest_configure``)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.engine import make_url

DISPOSABLE_DATABASE_SUFFIXES = ("_test", "_citest")
POSTGRES_DSN_FLAGS = (
    "PERSON_SEARCH_RUN_MIGRATION_INTEGRATION",
    "PERSON_SEARCH_RUN_ADAPTER_INTEGRATION",
    "PERSON_SEARCH_RUN_E2E",
)


def _database_name(dsn: str) -> str:
    try:
        return make_url(dsn).database or ""
    except Exception:  # noqa: BLE001 - an unparseable DSN is rejected like a wrong one
        return ""


def unsafe_test_databases(environment: Mapping[str, str | None]) -> list[tuple[str, str]]:
    """Return ``(variable, database)`` for DSNs that writing tests would use but are not disposable.

    Migration and E2E tests run ``alembic downgrade base``; the others insert fixture rows. Test
    modules call ``load_dotenv()``, so the demo DSN in ``backend/.env`` applies unless overridden.
    """

    dsn_variables = []
    if environment.get("PERSON_SEARCH_CAMERA_TEST_DSN"):
        dsn_variables.append("PERSON_SEARCH_CAMERA_TEST_DSN")
    if any(environment.get(flag) == "1" for flag in POSTGRES_DSN_FLAGS):
        dsn_variables.append("PERSON_SEARCH_POSTGRES_DSN")
    unsafe = []
    for variable in dsn_variables:
        database = _database_name(environment.get(variable, ""))
        if not database.endswith(DISPOSABLE_DATABASE_SUFFIXES):
            unsafe.append((variable, database or "<missing>"))
    return unsafe
