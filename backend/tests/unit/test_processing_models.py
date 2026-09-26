"""Unit tests for STO-05 processing and track models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import attributes

from person_search.storage.postgres.models import (
    AIConfigVersion,
    PersonTrack,
    ProcessingJob,
    StorageOutboxEvent,
    TrackIndexStatus,
)
from person_search.storage.postgres.models.person_track import reject_invalid_track_transition

pytestmark = pytest.mark.unit


def _track(status: TrackIndexStatus = TrackIndexStatus.PENDING) -> PersonTrack:
    return PersonTrack(
        camera_id=uuid.uuid4(),
        processing_job_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        appeared_at_utc=datetime.now(UTC),
        source_started_at_ms=0,
        source_ended_at_ms=1_000,
        representative_frame_timestamp_ms=500,
        bbox_x=10,
        bbox_y=20,
        bbox_width=100,
        bbox_height=200,
        frame_width=1_920,
        frame_height=1_080,
        encoder_version="reid-1",
        index_status=status,
    )


def test_sto05_tables_are_registered_without_matching_score() -> None:
    assert AIConfigVersion.__tablename__ == "ai_config_versions"
    assert ProcessingJob.__tablename__ == "processing_jobs"
    assert PersonTrack.__tablename__ == "person_tracks"
    assert StorageOutboxEvent.__tablename__ == "storage_outbox_events"
    assert "matching_score" not in PersonTrack.__table__.columns


def test_track_transition_pending_to_ready_is_allowed() -> None:
    track = _track()
    attributes.set_committed_value(track, "index_status", TrackIndexStatus.PENDING)
    track.index_status = TrackIndexStatus.READY
    reject_invalid_track_transition(None, None, track)


def test_track_transition_ready_to_failed_supports_reconciliation_quarantine() -> None:
    track = _track(TrackIndexStatus.READY)
    attributes.set_committed_value(track, "index_status", TrackIndexStatus.READY)
    track.index_status = TrackIndexStatus.FAILED

    reject_invalid_track_transition(None, None, track)


def test_track_transition_failed_to_pending_supports_retry() -> None:
    track = _track(TrackIndexStatus.FAILED)
    attributes.set_committed_value(track, "index_status", TrackIndexStatus.FAILED)
    track.index_status = TrackIndexStatus.PENDING
    reject_invalid_track_transition(None, None, track)
