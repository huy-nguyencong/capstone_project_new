from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import sessionmaker

from person_search.config import MilvusSettings, MinioSettings, PostgresSettings
from person_search.services.storage_maintenance import OutboxRetryWorker, StorageReconciler
from person_search.services.track_imagery import ImageVariant, TrackImageService
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.track_search import (
    CameraOutOfScopeError,
    TrackSearchQuery,
    TrackSearchService,
)
from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
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


class FlakyVectors:
    def __init__(self, inner: MilvusPersonTrackIndex) -> None:
        self.inner = inner
        self.encoder_version = inner.encoder_version
        self.failures = 0

    def upsert(self, **kwargs: object) -> None:
        if self.failures:
            self.failures -= 1
            raise TimeoutError("simulated Milvus outage")
        self.inner.upsert(**kwargs)  # type: ignore[arg-type]

    def get(self, track_id: uuid.UUID) -> dict[str, object] | None:
        return self.inner.get(track_id)


def _jpeg() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), "green").save(stream, format="JPEG")
    return stream.getvalue()


def test_retry_reconcile_search_and_imagery_on_real_storage() -> None:
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
        alias=f"person_track_read_{suffix}",
    )
    frames = MinioFrameStore(minio_storage.client, minio_settings.bucket)
    ids = {
        name: uuid.uuid4()
        for name in ("area_a", "area_b", "camera_a", "camera_b", "config", "job_a", "job_b")
    }
    operator_id, viewer_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    created_keys: list[str] = []

    def unit_of_work() -> UnitOfWork:
        return UnitOfWork(factory)

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    try:
        index.ensure_collection()
        with engine.begin() as connection:
            for area, code in (("area_a", "AREA-RA"), ("area_b", "AREA-RB")):
                connection.execute(
                    sa.text("INSERT INTO areas (id, code, name) VALUES (:id, :code, :code)"),
                    {"id": ids[area], "code": code},
                )
            for camera, area, code in (
                ("camera_a", "area_a", "CAM-RA"),
                ("camera_b", "area_b", "CAM-RB"),
            ):
                connection.execute(
                    sa.text(
                        "INSERT INTO cameras (id, area_id, code, name) "
                        "VALUES (:id, :area, :code, :code)"
                    ),
                    {"id": ids[camera], "area": ids[area], "code": code},
                )
            connection.execute(
                sa.text(
                    "INSERT INTO ai_config_versions "
                    "(id, version, detector_name, detector_version, tracker_name, "
                    "tracker_version, encoder_name, encoder_version, encoder_dimension, "
                    "checkpoint_sha256, status) VALUES "
                    "(:id, 'pipeline-r', 'yolo', '1', 'bytetrack', '1', 'rasa', :encoder, "
                    ":dimension, :sha, 'ACTIVE')"
                ),
                {
                    "id": ids["config"],
                    "encoder": encoder_version,
                    "dimension": len(VECTOR),
                    "sha": CHECKPOINT,
                },
            )
            for job, camera in (("job_a", "camera_a"), ("job_b", "camera_b")):
                connection.execute(
                    sa.text(
                        "INSERT INTO processing_jobs "
                        "(id, camera_id, ai_config_version_id, source_type, source_ref, "
                        "sampling_interval, timeline_origin_utc) VALUES "
                        "(:id, :camera, :config, 'FILE', 'clip.mp4', 5, :now)"
                    ),
                    {"id": ids[job], "camera": ids[camera], "config": ids["config"], "now": now},
                )
            connection.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, username, password_hash, display_name, role, assigned_area_id) VALUES "
                    "(:operator, 'operator-read', 'hash', 'Operator', 'OPERATOR', :area), "
                    "(:viewer, 'viewer-read', 'hash', 'Viewer', 'VIEWER', NULL)"
                ),
                {"operator": operator_id, "viewer": viewer_id, "area": ids["area_a"]},
            )

        def request(camera: str, job: str, area: str) -> TrackIngestionRequest:
            return TrackIngestionRequest(
                track_id=uuid.uuid4(),
                camera_id=ids[camera],
                area_id=ids[area],
                processing_job_id=ids[job],
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

        vectors = FlakyVectors(index)
        ingestion = TrackIngestionService(unit_of_work, frames, vectors)  # type: ignore[arg-type]
        track_a = request("camera_a", "job_a", "area_a")
        track_b = request("camera_b", "job_b", "area_b")
        vectors.failures = 1
        assert ingestion.ingest_track(track_a).status is TrackIndexStatus.PENDING
        assert ingestion.ingest_track(track_b).status is TrackIndexStatus.READY

        worker = OutboxRetryWorker(
            unit_of_work, ingestion, clock=lambda: datetime.now(UTC) + timedelta(minutes=1)
        )
        summary = worker.run_once()
        assert summary.claimed == 1 and summary.ready == 1
        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            event = work.repositories.outbox.get_for_track(track_a.track_id, "track.ingest")
            assert event is not None and event.status is OutboxStatus.COMPLETED
            for track in (track_a, track_b):
                stored = work.repositories.tracks.get(track.track_id)
                assert stored is not None and stored.minio_object_key is not None
                created_keys.append(stored.minio_object_key)
        milvus_storage.client.flush(index.collection_name)

        search = TrackSearchService(unit_of_work, index)
        results = search.search(operator_id, TrackSearchQuery(VECTOR, top_k=4))
        assert [result.track_id for result in results] == [track_a.track_id]
        with pytest.raises(CameraOutOfScopeError):
            search.search(
                operator_id, TrackSearchQuery(VECTOR, top_k=4, camera_ids=(ids["camera_b"],))
            )

        imagery = TrackImageService(unit_of_work, frames)
        crop = imagery.search_result_image(
            operator_id, track_a.track_id, ImageVariant.PERSON_CROP
        )
        assert (crop.width, crop.height) == (20, 40)

        with engine.begin() as connection:
            case_id, result_id = uuid.uuid4(), uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO cases (id, owner_user_id, title) VALUES (:id, :owner, 'Case')"
                ),
                {"id": case_id, "owner": operator_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO case_results (id, case_id, track_id, camera_name_snapshot, "
                    "area_name_snapshot, appeared_at_snapshot) VALUES "
                    "(:id, :case, :track, 'CAM-RA', 'AREA-RA', :now)"
                ),
                {"id": result_id, "case": case_id, "track": track_a.track_id, "now": now},
            )
        frame = imagery.case_result_image(viewer_id, result_id, ImageVariant.FULL_FRAME)
        assert (frame.width, frame.height) == (64, 48)

        orphan_key = (
            f"tracks/v1/{ids['camera_a']}/2026/09/25/{uuid.uuid4()}/representative.jpg"
        )
        minio_storage.client.put_object(
            minio_settings.bucket,
            orphan_key,
            io.BytesIO(b"orphan"),
            6,
            content_type="image/jpeg",
            metadata={"sha256": "0" * 64},
        )
        created_keys.append(orphan_key)
        reconciler = StorageReconciler(
            unit_of_work, frames, index, frame_prefix=f"tracks/v1/{ids['camera_a']}"
        )
        dry_run = reconciler.run()
        assert orphan_key in dry_run.orphan_objects
        assert dry_run.missing_objects == [] and dry_run.missing_vectors == []
        assert frames.head_frame(orphan_key) is not None
        deleted = reconciler.run(delete_orphans=True)
        assert orphan_key in deleted.deleted_objects
    finally:
        for key in created_keys:
            try:
                frames.delete_frame(key)
            except Exception:
                pass
        if milvus_storage.client.has_collection(index.collection_name):
            aliases = milvus_storage.client.list_aliases(index.collection_name).get("aliases", [])
            if index.alias in aliases:
                milvus_storage.client.drop_alias(index.alias)
            milvus_storage.client.drop_collection(index.collection_name)
        minio_storage.close()
        milvus_storage.close()
        engine.dispose()
        command.downgrade(alembic_config, "base")
