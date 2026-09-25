"""Unit tests for Milvus vector validation and safe filters."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from person_search.storage.milvus.vectors import (
    InvalidVectorError,
    MilvusPersonTrackIndex,
    VectorFilter,
)

pytestmark = pytest.mark.unit


def test_vector_validation_rejects_dimension_nonfinite_and_non_normalized() -> None:
    index = MilvusPersonTrackIndex(MagicMock(), encoder_version="encoder_v1", dimension=2)
    assert index.validate_vector([1.0, 0.0]) == [1.0, 0.0]
    for vector in ([1.0], [math.nan, 0.0], [2.0, 0.0]):
        with pytest.raises(InvalidVectorError):
            index.validate_vector(vector)


def test_filter_expression_is_built_only_from_typed_values() -> None:
    area_id = uuid.uuid4()
    camera_id = uuid.uuid4()
    filters = VectorFilter(
        area_id,
        camera_id,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )
    expression = filters.expression()
    assert str(area_id) in expression
    assert str(camera_id) in expression
    assert 'index_status == "READY"' in expression


def test_upsert_never_persists_a_matching_score() -> None:
    client = MagicMock()
    index = MilvusPersonTrackIndex(client, encoder_version="encoder_v1", dimension=2)
    index.upsert(
        track_id=uuid.uuid4(),
        vector=[1.0, 0.0],
        area_id=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        appeared_at=datetime.now(UTC),
    )
    data = client.upsert.call_args.kwargs["data"]
    assert "score" not in data
    assert "matching_score" not in data
