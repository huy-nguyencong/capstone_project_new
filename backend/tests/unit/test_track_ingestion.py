from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from ingestion_harness import FRAME_WIDTH, NOW, Harness, jpeg_frame

from person_search.services.track_ingestion import (
    RetryPolicy,
    TrackIngestionConflictError,
    TrackReferenceError,
)
from person_search.storage.contracts import RASA_EMBEDDING_DIMENSION
from person_search.storage.postgres.models import OutboxStatus, TrackIndexStatus

pytestmark = pytest.mark.unit


def test_happy_path_writes_same_track_id_to_all_three_stores() -> None:
    harness = Harness()
    request = harness.request()

    result = harness.service.ingest_track(request, correlation_id="corr-1")

    assert result.status is TrackIndexStatus.READY
    assert result.correlation_id == "corr-1"
    harness.assert_converged(request)
    row = harness.milvus.rows[str(request.track_id)]
    assert row["area_id"] == str(harness.area_id)
    assert row["camera_id"] == str(harness.camera_id)
    payload = harness.event(request.track_id).payload
    assert payload["correlation_id"] == "corr-1"
    assert payload["frame_sha256"] == request.frame_sha256
    assert len(payload["embedding"]) == RASA_EMBEDDING_DIMENSION
    assert "frame_bytes" not in payload


def test_retry_of_ready_track_is_a_no_op() -> None:
    harness = Harness()
    request = harness.request()
    harness.service.ingest_track(request)

    result = harness.service.ingest_track(request)

    assert result.status is TrackIndexStatus.READY
    assert harness.minio.puts == 1
    assert harness.milvus.upserts == 1


def test_postgres_insert_failure_creates_no_external_artifacts() -> None:
    harness = Harness()
    request = harness.request()
    harness.database.commit_failures[1] = ConnectionError("database unavailable")

    with pytest.raises(ConnectionError):
        harness.service.ingest_track(request)

    assert harness.database.tracks == {}
    assert harness.minio.objects == {}
    assert harness.milvus.rows == {}
    assert harness.service.ingest_track(request).status is TrackIndexStatus.READY
    harness.assert_converged(request)


@pytest.mark.parametrize("step", ["frame", "vector", "publish"])
def test_transient_failure_stays_pending_then_retry_converges(step: str) -> None:
    harness = Harness()
    request = harness.request()
    if step == "frame":
        harness.minio.failures.append(ConnectionError("minio unavailable"))
    elif step == "vector":
        harness.milvus.failures.append(TimeoutError("milvus timeout"))
    else:
        harness.database.commit_failures[2] = ConnectionError("final commit lost")

    first = harness.service.ingest_track(request)

    assert first.status is TrackIndexStatus.PENDING
    assert first.retryable is True
    track = harness.database.tracks[request.track_id]
    assert track.index_status is TrackIndexStatus.PENDING
    assert track.vector_indexed_at is None
    event = harness.event(request.track_id)
    assert event.status is OutboxStatus.PENDING
    assert event.attempts == 1
    assert event.available_at == NOW + timedelta(seconds=2)

    second = harness.service.ingest_track(request)

    assert second.status is TrackIndexStatus.READY
    harness.assert_converged(request)


def test_non_retryable_frame_error_fails_without_vector() -> None:
    harness = Harness()
    request = harness.request(frame_width=FRAME_WIDTH + 1)

    result = harness.service.ingest_track(request)

    assert result.status is TrackIndexStatus.FAILED
    assert result.failure_code == "FRAME_UPLOAD_FAILED"
    assert harness.database.tracks[request.track_id].index_status is TrackIndexStatus.FAILED
    assert harness.event(request.track_id).status is OutboxStatus.DEAD
    assert harness.milvus.rows == {}
    assert harness.service.ingest_track(request).status is TrackIndexStatus.FAILED
    assert harness.minio.puts == 0


def test_exhausted_retries_mark_track_failed_and_event_dead() -> None:
    harness = Harness(RetryPolicy(max_attempts=2))
    request = harness.request()
    harness.milvus.failures.extend([TimeoutError("down"), TimeoutError("down")])

    assert harness.service.ingest_track(request).status is TrackIndexStatus.PENDING
    result = harness.service.ingest_track(request)

    assert result.status is TrackIndexStatus.FAILED
    assert result.retryable is False
    event = harness.event(request.track_id)
    assert event.status is OutboxStatus.DEAD
    assert event.attempts == 2
    track = harness.database.tracks[request.track_id]
    assert track.failure_code == "VECTOR_UPSERT_FAILED"
    assert "down" not in (track.failure_message or "")


def test_same_track_id_with_different_frame_is_a_conflict() -> None:
    harness = Harness()
    track_id = uuid.uuid4()
    harness.service.ingest_track(harness.request(track_id=track_id))

    with pytest.raises(TrackIngestionConflictError):
        harness.service.ingest_track(harness.request(track_id=track_id, frame=jpeg_frame("red")))

    assert harness.minio.puts == 1


def test_camera_area_mismatch_is_rejected_before_any_write() -> None:
    harness = Harness()

    with pytest.raises(TrackReferenceError):
        harness.service.ingest_track(harness.request(area_id=uuid.uuid4()))

    assert harness.database.tracks == {}
    assert harness.database.events == {}
    assert harness.minio.objects == {}
    assert harness.milvus.rows == {}


def test_encoder_mismatch_with_ai_config_is_rejected() -> None:
    harness = Harness()
    harness.database.configs[harness.config_id].checkpoint_sha256 = "cd" * 32

    with pytest.raises(TrackReferenceError):
        harness.service.ingest_track(harness.request())

    assert harness.database.tracks == {}


def test_retry_policy_backoff_is_capped() -> None:
    policy = RetryPolicy(max_attempts=10, base_delay_seconds=2, max_delay_seconds=10)

    assert [policy.delay_after(n).total_seconds() for n in range(1, 5)] == [2, 4, 8, 10]
