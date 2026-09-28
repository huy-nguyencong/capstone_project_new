from __future__ import annotations

import pytest
from database_guard import unsafe_test_databases

pytestmark = pytest.mark.unit

DEMO = "postgresql+psycopg://person_search:secret@127.0.0.1:5432/person_search"
CITEST = "postgresql+psycopg://person_search:secret@127.0.0.1:5432/person_search_citest"


def test_no_writing_suite_enabled_is_safe_even_with_demo_dsn() -> None:
    assert unsafe_test_databases({"PERSON_SEARCH_POSTGRES_DSN": DEMO}) == []


@pytest.mark.parametrize(
    "flag",
    [
        "PERSON_SEARCH_RUN_MIGRATION_INTEGRATION",
        "PERSON_SEARCH_RUN_ADAPTER_INTEGRATION",
        "PERSON_SEARCH_RUN_E2E",
    ],
)
def test_flagged_suite_on_demo_database_is_rejected(flag: str) -> None:
    environment = {flag: "1", "PERSON_SEARCH_POSTGRES_DSN": DEMO}

    assert unsafe_test_databases(environment) == [("PERSON_SEARCH_POSTGRES_DSN", "person_search")]


def test_camera_dsn_on_demo_database_is_rejected() -> None:
    environment = {"PERSON_SEARCH_CAMERA_TEST_DSN": DEMO}

    assert unsafe_test_databases(environment) == [
        ("PERSON_SEARCH_CAMERA_TEST_DSN", "person_search")
    ]


def test_disposable_databases_are_accepted() -> None:
    environment = {
        "PERSON_SEARCH_RUN_E2E": "1",
        "PERSON_SEARCH_POSTGRES_DSN": CITEST,
        "PERSON_SEARCH_CAMERA_TEST_DSN": DEMO.replace("/person_search", "/person_search_test"),
    }

    assert unsafe_test_databases(environment) == []


@pytest.mark.parametrize("dsn", [None, "", "not a dsn"])
def test_missing_or_unparseable_dsn_is_rejected(dsn: str | None) -> None:
    environment = {"PERSON_SEARCH_RUN_E2E": "1", "PERSON_SEARCH_POSTGRES_DSN": dsn}

    assert unsafe_test_databases(environment) == [("PERSON_SEARCH_POSTGRES_DSN", "<missing>")]
