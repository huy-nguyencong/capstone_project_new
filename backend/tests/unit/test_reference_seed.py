"""Safety checks for the explicit reference-data seed."""

from __future__ import annotations

import pytest

from person_search.storage.postgres.seed import DEVELOPMENT_AREAS

pytestmark = pytest.mark.unit


def test_seed_contains_only_stable_non_secret_area_rows() -> None:
    assert len(DEVELOPMENT_AREAS) == 2
    assert len({row[0] for row in DEVELOPMENT_AREAS}) == 2
    assert len({row[1] for row in DEVELOPMENT_AREAS}) == 2
    serialized = repr(DEVELOPMENT_AREAS).lower()
    assert "password" not in serialized
    assert "secret" not in serialized
