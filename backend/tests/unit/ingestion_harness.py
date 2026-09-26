from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from PIL import Image
from storage_fakes import FakeDatabase, FakeMilvusClient, FakeMinioClient, FakeUnitOfWork

from person_search.services.track_ingestion import (
    TRACK_INGEST_EVENT,
    RetryPolicy,
    TrackIngestionService,
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
from person_search.storage.postgres.models import (
    CameraStatus,
    OutboxStatus,
    StorageOutboxEvent,
    TrackIndexStatus,
)

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)
CHECKPOINT = "ab" * 32
FRAME_WIDTH, FRAME_HEIGHT = 64, 48


def jpeg_frame(color: str = "green") -> bytes:
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
        self.database.cameras[self.camera_id] = SimpleNamespace(
            area_id=self.area_id, status=CameraStatus.ACTIVE
        )
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
            frame_bytes=frame or jpeg_frame(),
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
        assert track.vector_indexed_at is not None and track.vector_indexed_at >= NOW
        assert track.failure_code is None
        assert list(self.database.tracks) == [request.track_id]
        assert list(self.minio.objects) == [key]
        assert list(self.milvus.rows) == [str(request.track_id)]
        assert self.event(request.track_id).status is OutboxStatus.COMPLETED
