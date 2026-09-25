"""Safety checks for the explicit reference-data seed."""

from __future__ import annotations

import pytest

from person_search.storage.postgres.seed import (
    DEVELOPMENT_AREAS,
    DEVELOPMENT_PASSWORD,
    DEVELOPMENT_USERS,
    seed_development_users,
)

pytestmark = pytest.mark.unit


def test_seed_contains_stable_area_rows() -> None:
    assert len(DEVELOPMENT_AREAS) == 2
    assert len({row[0] for row in DEVELOPMENT_AREAS}) == 2
    assert len({row[1] for row in DEVELOPMENT_AREAS}) == 2


def test_seed_contains_one_stable_user_per_role() -> None:
    assert [row[1] for row in DEVELOPMENT_USERS] == ["admin", "operator", "viewer"]
    assert [row[3] for row in DEVELOPMENT_USERS] == ["ADMIN", "OPERATOR", "VIEWER"]
    assert len({row[0] for row in DEVELOPMENT_USERS}) == 3
    assert DEVELOPMENT_USERS[1][4] == "GATE-A"
    assert DEVELOPMENT_USERS[0][4] is None
    assert DEVELOPMENT_USERS[2][4] is None
    assert DEVELOPMENT_PASSWORD == "password"


def test_development_users_are_refused_in_production() -> None:
    with pytest.raises(RuntimeError, match="cannot be seeded in production"):
        seed_development_users({"PERSON_SEARCH_ENV": "production"})
