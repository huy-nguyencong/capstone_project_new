from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from PIL import Image

from person_search.services.track_ingestion import (
    TRACK_INGEST_EVENT,
    RetryPolicy,
    TrackIngestionConflictError,
    TrackIngestionService,
    TrackReferenceError,
)
from person_search.storage.contracts import (
    RASA_EMBEDDING_DIMENSION,
    RASA_ENCODER_VERSION,
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
    frame_object_key,
)
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    OutboxStatus,
    PersonTrack,
    StorageOutboxEvent,
    TrackIndexStatus,
)
from person_search.storage.postgres.models.person_track import ALLOWED_TRACK_TRANSITIONS

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)
CHECKPOINT = "ab" * 32
FRAME_WIDTH, FRAME_HEIGHT = 64, 48


def _clone(entity: Any) -> Any:
    mapper = sa.inspect(type(entity))
    values = {attribute.key: getattr(entity, attribute.key) for attribute in mapper.column_attrs}
    return type(entity)(**values)


class FakeDatabase:
    def __init__(self) -> None:
        self.cameras: dict[uuid.UUID, Any] = {}
        self.jobs: dict[uuid.UUID, Any] = {}
        self.configs: dict[uuid.UUID, Any] = {}
        self.tracks: dict[uuid.UUID, PersonTrack] = {}
        self.events: dict[tuple[uuid.UUID, str], StorageOutboxEvent] = {}
        self.commits = 0
        self.commit_failures: dict[int, Exception] = {}


class FakeLookup:
    def __init__(self, rows: dict[uuid.UUID, Any]) -> None:
        self.rows = rows

    def get(self, entity_id: uuid.UUID) -> Any:
        return self.rows.get(entity_id)


class FakeTracks:
    def __init__(self, rows: dict[uuid.UUID, PersonTrack]) -> None:
        self.rows = rows

    def add(self, track: PersonTrack) -> None:
        if track.id in self.rows:
            raise DuplicateEntityError("duplicate track")
        self.rows[track.id] = track

    def get_for_update(self, track_id: uuid.UUID) -> PersonTrack | None:
        return self.rows.get(track_id)


class FakeOutbox:
    def __init__(self, rows: dict[tuple[uuid.UUID, str], StorageOutboxEvent]) -> None:
        self.rows = rows

    def add(self, event: StorageOutboxEvent) -> None:
        key = (event.track_id, event.event_type)
        if key in self.rows:
            raise DuplicateEntityError("duplicate outbox event")
        self.rows[key] = event

    def get_for_track(
        self, track_id: uuid.UUID, event_type: str, *, for_update: bool = False
    ) -> StorageOutboxEvent | None:
        return self.rows.get((track_id, event_type))


class FakeUnitOfWork:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.repositories: Any = None

    def __enter__(self) -> FakeUnitOfWork:
        self.tracks = {key: _clone(value) for key, value in self.database.tracks.items()}
        self.events = {key: _clone(value) for key, value in self.database.events.items()}
        self.repositories = SimpleNamespace(
            cameras=FakeLookup(self.database.cameras),
            jobs=FakeLookup(self.database.jobs),
            ai_configs=FakeLookup(self.database.configs),
            tracks=FakeTracks(self.tracks),
            outbox=FakeOutbox(self.events),
        )
        return self

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.database.commits += 1
        failure = self.database.commit_failures.pop(self.database.commits, None)
        if failure is not None:
            raise failure
        for track_id, track in self.tracks.items():
            previous = self.database.tracks.get(track_id)
            if previous is not None:
                allowed = ALLOWED_TRACK_TRANSITIONS[previous.index_status]
                assert track.index_status in allowed
            if track.index_status is TrackIndexStatus.READY:
                assert track.minio_object_key and track.frame_sha256
                assert track.frame_size_bytes and track.vector_indexed_at is not None
        for key in self.events:
            assert key[0] in self.tracks
        self.database.tracks = self.tracks
        self.database.events = self.events

    def __exit__(self, *args: object) -> None:
        pass


class MissingObject(Exception):
    code = "NoSuchKey"


class FakeResponse(io.BytesIO):
    def release_conn(self) -> None:
        pass


class FakeMinioClient:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str, dict[str, str]]] = {}
        self.puts = 0
        self.failures: list[Exception] = []

    def stat_object(self, bucket: str, key: str) -> SimpleNamespace:
        if key not in self.objects:
            raise MissingObject()
        data, content_type, metadata = self.objects[key]
        return SimpleNamespace(size=len(data), content_type=content_type, metadata=metadata)

    def put_object(
        self,
        bucket: str,
        key: str,
        stream: io.BytesIO,
        length: int,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.puts += 1
        self.objects[key] = (stream.read(length), content_type, metadata)

    def get_object(self, bucket: str, key: str) -> FakeResponse:
        return FakeResponse(self.objects[key][0])


class FakeMilvusClient:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.upserts = 0
        self.failures: list[Exception] = []

    def upsert(self, collection_name: str, *, data: dict[str, Any], timeout: int) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.upserts += 1
        self.rows[data["track_id"]] = data


def _jpeg(color: str = "green") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), color).save(stream, format="JPEG")
    return stream.getvalue()


class Harness:
    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self.database = FakeDatabase()
        self.minio = FakeMinioClient()
        self.milvus = FakeMilvusClient()
        self.area_id, self.camera_id = uuid.uuid4(), uuid.uuid4()
        self.job_id, self.config_id = uuid.uuid4(), uuid.uuid4()
        self.database.cameras[self.camera_id] = SimpleNamespace(area_id=self.area_id)
        self.database.jobs[self.job_id] = SimpleNamespace(
            camera_id=self.camera_id, ai_config_version_id=self.config_id
        )
        self.database.configs[self.config_id] = SimpleNamespace(
            encoder_version=RASA_ENCODER_VERSION,
            encoder_dimension=RASA_EMBEDDING_DIMENSION,
            checkpoint_sha256=CHECKPOINT,
        )
        self.service = TrackIngestionService(
            lambda: FakeUnitOfWork(self.database),  # type: ignore[arg-type,return-value]
            MinioFrameStore(self.minio, "frames"),
            MilvusPersonTrackIndex(
                self.milvus,
                encoder_version=RASA_ENCODER_VERSION,
                dimension=RASA_EMBEDDING_DIMENSION,
            ),
            retry_policy=retry_policy,
            clock=lambda: NOW,
        )

    def request(
        self,
        *,
        track_id: uuid.UUID | None = None,
        frame: bytes | None = None,
        area_id: uuid.UUID | None = None,
        frame_width: int = FRAME_WIDTH,
    ) -> TrackIngestionRequest:
        return TrackIngestionRequest(
            track_id=track_id or uuid.uuid4(),
            camera_id=self.camera_id,
            area_id=area_id or self.area_id,
            processing_job_id=self.job_id,
            ai_config_version_id=self.config_id,
            timeline_origin_utc=NOW,
            source_frame_index=30,
            source_started_at_ms=1_000,
            representative_frame_timestamp_ms=1_500,
            source_ended_at_ms=2_000,
            bbox=BoundingBoxPixels(
                x=4, y=2, width=20, height=40, frame_width=frame_width, frame_height=FRAME_HEIGHT
            ),
            frame_bytes=frame or _jpeg(),
            embedding=[1.0] + [0.0] * (RASA_EMBEDDING_DIMENSION - 1),
            encoder=EncoderManifest(
                version=RASA_ENCODER_VERSION,
                embedding_dimension=RASA_EMBEDDING_DIMENSION,
                checkpoint_sha256=CHECKPOINT,
            ),
        )

    def event(self, track_id: uuid.UUID) -> StorageOutboxEvent:
        return self.database.events[(track_id, TRACK_INGEST_EVENT)]

    def assert_converged(self, request: TrackIngestionRequest) -> None:
        track = self.database.tracks[request.track_id]
        key = frame_object_key(request.camera_id, request.appeared_at_utc, request.track_id)
        assert track.index_status is TrackIndexStatus.READY
        assert track.minio_object_key == key
        assert track.frame_sha256 == request.frame_sha256
        assert track.vector_indexed_at == NOW
        assert track.failure_code is None
        assert list(self.database.tracks) == [request.track_id]
        assert list(self.minio.objects) == [key]
        assert list(self.milvus.rows) == [str(request.track_id)]
        assert self.event(request.track_id).status is OutboxStatus.COMPLETED


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
        harness.service.ingest_track(harness.request(track_id=track_id, frame=_jpeg("red")))

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
