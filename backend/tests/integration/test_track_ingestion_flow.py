from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import sessionmaker

from person_search.config import MilvusSettings, MinioSettings, PostgresSettings
from person_search.services.track_ingestion import TrackIngestionService
from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex, VectorFilter
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import OutboxStatus, TrackIndexStatus
from person_search.storage.postgres.unit_of_work import UnitOfWork

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1"
        or os.getenv("PERSON_SEARCH_RUN_ADAPTER_INTEGRATION") != "1",
        reason="set migration and adapter integration flags with the local storage stack",
    ),
]

CHECKPOINT = "ab" * 32
VECTOR = [1.0, 0.0, 0.0, 0.0]


class FlakyFrameStore:
    def __init__(self, inner: MinioFrameStore) -> None:
        self.inner = inner
        self.failures = 1

    def put_frame(self, **kwargs: Any) -> Any:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("simulated MinIO outage")
        return self.inner.put_frame(**kwargs)


def _jpeg() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(stream, format="JPEG")
    return stream.getvalue()


def test_ingest_track_converges_across_postgres_minio_and_milvus() -> None:
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    alembic_config = Config("alembic.ini")
    minio_settings = MinioSettings.from_environment(os.environ)
    minio_storage = MinioStorage(minio_settings)
    milvus_settings = MilvusSettings.from_environment(os.environ)
    milvus_storage = MilvusStorage(milvus_settings)
    suffix = uuid.uuid4().hex[:8]
    encoder_version = f"integration_{suffix}"
    index = MilvusPersonTrackIndex(
        milvus_storage.client,
        encoder_version=encoder_version,
        dimension=len(VECTOR),
        timeout=milvus_settings.timeout_seconds,
        alias=f"person_track_ingest_{suffix}",
    )
    frames = MinioFrameStore(minio_storage.client, minio_settings.bucket)
    ids = {name: uuid.uuid4() for name in ("area", "camera", "config", "job")}
    now = datetime.now(UTC).replace(microsecond=0)
    created_keys: list[str] = []

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    try:
        index.ensure_collection()
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO areas (id, code, name) VALUES (:id, 'AREA-I', 'Area I')"),
                {"id": ids["area"]},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cameras (id, area_id, code, name) "
                    "VALUES (:id, :area, 'CAM-I', 'Camera I')"
                ),
                {"id": ids["camera"], "area": ids["area"]},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO ai_config_versions "
                    "(id, version, detector_name, detector_version, tracker_name, "
                    "tracker_version, encoder_name, encoder_version, encoder_dimension, "
                    "checkpoint_sha256, status) VALUES "
                    "(:id, 'pipeline-i', 'yolo', '1', 'bytetrack', '1', 'rasa', :encoder, "
                    ":dimension, :sha, 'ACTIVE')"
                ),
                {
                    "id": ids["config"],
                    "encoder": encoder_version,
                    "dimension": len(VECTOR),
                    "sha": CHECKPOINT,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO processing_jobs "
                    "(id, camera_id, ai_config_version_id, source_type, source_ref, "
                    "sampling_interval, timeline_origin_utc) VALUES "
                    "(:id, :camera, :config, 'FILE', 'clip.mp4', 5, :now)"
                ),
                {"id": ids["job"], "camera": ids["camera"], "config": ids["config"], "now": now},
            )

        def request() -> TrackIngestionRequest:
            return TrackIngestionRequest(
                track_id=uuid.uuid4(),
                camera_id=ids["camera"],
                area_id=ids["area"],
                processing_job_id=ids["job"],
                ai_config_version_id=ids["config"],
                timeline_origin_utc=now,
                source_frame_index=30,
                source_started_at_ms=1_000,
                representative_frame_timestamp_ms=1_500,
                source_ended_at_ms=2_000,
                bbox=BoundingBoxPixels(
                    x=4, y=2, width=20, height=40, frame_width=64, frame_height=48
                ),
                frame_bytes=_jpeg(),
                embedding=VECTOR,
                encoder=EncoderManifest(
                    version=encoder_version,
                    embedding_dimension=len(VECTOR),
                    checkpoint_sha256=CHECKPOINT,
                ),
            )

        flaky = FlakyFrameStore(frames)
        service = TrackIngestionService(lambda: UnitOfWork(factory), flaky, index)
        ready_request, pending_request = request(), request()

        assert service.ingest_track(ready_request).status is TrackIndexStatus.PENDING
        assert service.ingest_track(ready_request).status is TrackIndexStatus.READY
        assert service.ingest_track(ready_request).status is TrackIndexStatus.READY

        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            track = work.repositories.tracks.get(ready_request.track_id)
            event = work.repositories.outbox.get_for_track(ready_request.track_id, "track.ingest")
            assert track is not None and event is not None
            assert track.index_status is TrackIndexStatus.READY
            assert event.status is OutboxStatus.COMPLETED
            assert event.attempts == 1
            assert track.minio_object_key is not None
            created_keys.append(track.minio_object_key)
        assert frames.head_frame(created_keys[0]).checksum_sha256 == ready_request.frame_sha256
        assert index.get(ready_request.track_id) is not None

        flaky.failures = 1
        assert service.ingest_track(pending_request).status is TrackIndexStatus.PENDING
        index.upsert(
            track_id=pending_request.track_id,
            vector=VECTOR,
            area_id=ids["area"],
            camera_id=ids["camera"],
            appeared_at=pending_request.appeared_at_utc,
        )
        milvus_storage.client.flush(index.collection_name)

        hits = index.search(VECTOR, VectorFilter(area_id=ids["area"]), top_k=4)
        assert {hit.track_id for hit in hits} == {
            ready_request.track_id,
            pending_request.track_id,
        }
        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            ready = work.repositories.tracks.ready_ids(hit.track_id for hit in hits)
        assert ready == {ready_request.track_id}
    finally:
        for key in created_keys:
            frames.delete_frame(key)
        if milvus_storage.client.has_collection(index.collection_name):
            aliases = milvus_storage.client.list_aliases(index.collection_name).get("aliases", [])
            if index.alias in aliases:
                milvus_storage.client.drop_alias(index.alias)
            milvus_storage.client.drop_collection(index.collection_name)
        minio_storage.close()
        milvus_storage.close()
        engine.dispose()
        command.downgrade(alembic_config, "base")
