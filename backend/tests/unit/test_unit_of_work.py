"""Unit tests for repository and UnitOfWork contracts."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from person_search.storage.postgres.errors import DuplicateEntityError, InvalidEntityError
from person_search.storage.postgres.unit_of_work import UnitOfWork, map_integrity_error

pytestmark = pytest.mark.unit


class _DatabaseError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate


def test_integrity_errors_are_mapped_to_domain_errors() -> None:
    duplicate = IntegrityError("statement", {}, _DatabaseError("23505"))
    invalid = IntegrityError("statement", {}, _DatabaseError("23514"))
    assert isinstance(map_integrity_error(duplicate), DuplicateEntityError)
    assert isinstance(map_integrity_error(invalid), InvalidEntityError)


def test_unit_of_work_rolls_back_exception_and_closes_session() -> None:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    with pytest.raises(RuntimeError):
        with UnitOfWork(factory):
            raise RuntimeError("failed service operation")
    session.rollback.assert_called_once()
    session.close.assert_called_once()


def test_unit_of_work_commit_maps_and_rolls_back_integrity_failure() -> None:
    session = MagicMock()
    session.commit.side_effect = IntegrityError("statement", {}, _DatabaseError("23505"))
    with UnitOfWork(MagicMock(return_value=session)) as work:
        with pytest.raises(DuplicateEntityError):
            work.commit()
    session.rollback.assert_called_once()
