"""Unit tests for STO-06 case ownership and schema contracts."""

from __future__ import annotations

import uuid

import pytest

from person_search.services.case_policy import (
    CaseOwnerNotAllowedError,
    owner_id_from_authenticated_actor,
)
from person_search.storage.postgres.models import AuditLog, Case, CaseResult, UserRole

pytestmark = pytest.mark.unit


def test_case_schema_excludes_status_area_and_matching_score() -> None:
    assert {"status", "area_id", "matching_score"}.isdisjoint(Case.__table__.columns.keys())
    assert "matching_score" not in CaseResult.__table__.columns
    assert AuditLog.__table__.columns["metadata"].nullable is False


def test_case_result_allows_same_track_to_be_saved_more_than_once() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in CaseResult.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("case_id", "track_id") not in unique_column_sets


def test_case_owner_is_derived_from_operator_session() -> None:
    actor_id = uuid.uuid4()
    assert owner_id_from_authenticated_actor(actor_id, UserRole.OPERATOR) == actor_id

    for role in (UserRole.ADMIN, UserRole.VIEWER):
        with pytest.raises(CaseOwnerNotAllowedError):
            owner_id_from_authenticated_actor(actor_id, role)
