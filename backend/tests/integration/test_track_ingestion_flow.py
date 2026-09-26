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
from person_search.storage.postgres.models import JobSourceType, OutboxStatus, TrackIndexStatus
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.workers.contracts import (
    CompletedTrack,
    EmbeddingVector,
    ModelLineage,
    QualityComponent,
    QualityFlag,
    RepresentativeCandidate,
    SourceFrame,
)
from person_search.workers.durable import JobExecutionSnapshot
from person_search.workers.production import EncodedTrack, ProductionPipelineResult
from person_search.workers.publication import (
    BundleImporter,
    BundlePublisher,
    ProductionTrackPublisher,
    stable_track_id,
)

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


class FlakyVectorIndex:
    def __init__(self, inner: MilvusPersonTrackIndex) -> None:
        self.inner = inner
        self.encoder_version = inner.encoder_version
        self.failures = 1

    def upsert(self, **kwargs: Any) -> Any:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("simulated Milvus outage")
        return self.inner.upsert(**kwargs)

    def get(self, track_id: uuid.UUID) -> Any:
        return self.inner.get(track_id)


def _jpeg() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(stream, format="JPEG")
    return stream.getvalue()


def test_ingest_track_converges_across_postgres_minio_and_milvus(tmp_path) -> None:
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
        ready_request, pending_request, vector_retry_request = request(), request(), request()

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

        flaky_vectors = FlakyVectorIndex(index)
        vector_service = TrackIngestionService(
            lambda: UnitOfWork(factory), frames, flaky_vectors
        )
        first = vector_service.ingest_track(vector_retry_request)
        assert first.status is TrackIndexStatus.PENDING and first.retryable
        assert index.get(vector_retry_request.track_id) is None
        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            partial = work.repositories.tracks.get(vector_retry_request.track_id)
            assert partial is not None and partial.index_status is TrackIndexStatus.PENDING
            assert partial.minio_object_key is not None
            created_keys.append(partial.minio_object_key)
        assert (
            frames.head_frame(created_keys[-1]).checksum_sha256
            == vector_retry_request.frame_sha256
        )

        assert vector_service.ingest_track(vector_retry_request).status is TrackIndexStatus.READY
        assert vector_service.ingest_track(vector_retry_request).status is TrackIndexStatus.READY
        assert index.get(vector_retry_request.track_id) is not None

        image = Image.new("RGB", (64, 48), "blue")
        lineage = ModelLineage("rasa", encoder_version, CHECKPOINT)
        completed = CompletedTrack(
            ids["camera"],
            ids["job"],
            ids["config"],
            "integration-local-1",
            1_000,
            2_000,
            RepresentativeCandidate(
                SourceFrame(ids["camera"], 30, 1_500, image, 64, 48),
                BoundingBoxPixels(4, 2, 20, 40, 64, 48),
                (QualityComponent("sharpness", 1.0),),
                1.0,
            ),
            QualityFlag.ACCEPTED,
            5,
            ModelLineage("yolo", "1", "cd" * 32),
            ModelLineage("bytetrack", "1", "ef" * 32),
            lineage,
        )
        encoded = EncodedTrack(completed, EmbeddingVector(tuple(VECTOR), 4, True, lineage))
        snapshot = JobExecutionSnapshot(
            ids["job"],
            uuid.uuid4(),
            ids["camera"],
            ids["config"],
            JobSourceType.FILE,
            "clip.mp4",
            5,
            now,
            1,
        )
        result = ProductionPipelineResult(40, 8, 1, 1, (encoded,), ())

        class Jobs:
            calls: list[tuple[Any, ...]] = []

            def checkpoint(self, *args: Any) -> bool:
                self.calls.append(args)
                return True

        jobs = Jobs()
        ProductionTrackPublisher(service, ids["area"], jobs)(snapshot, result)
        assert jobs.calls[-1][-2:] == (1, 1)
        published_id = stable_track_id(ids["job"], "integration-local-1")
        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            published = work.repositories.tracks.get(published_id)
            assert published is not None and published.index_status is TrackIndexStatus.READY
            assert published.minio_object_key is not None
            created_keys.append(published.minio_object_key)

        bundle_path = tmp_path / "aiw18-bundle.json"
        BundlePublisher().write(bundle_path, snapshot, ids["area"], result)
        importer = BundleImporter(
            service,
            ids["config"],
            EncoderManifest(encoder_version, len(VECTOR), CHECKPOINT),
        )
        assert importer.import_file(bundle_path) == 1
        assert importer.import_file(bundle_path) == 1
        assert index.get(published_id) is not None
        image.close()
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
