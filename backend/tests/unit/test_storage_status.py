from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from ingestion_harness import NOW, Harness
from storage_fakes import FakeUnitOfWork

from person_search.services.storage_status import (
    StatusAccessDeniedError,
    StorageComponent,
    StorageMetrics,
    StorageStatusService,
)
from person_search.services.track_imagery import ImageVariant, TrackImageService
from person_search.storage.postgres.models import TrackIndexStatus, UserRole, UserStatus

pytestmark = pytest.mark.unit


def test_metrics_track_component_errors_and_ingestion_timings() -> None:
    metrics = StorageMetrics(clock=lambda: NOW)

    metrics.record_error(StorageComponent.MILVUS, TimeoutError("down"))
    metrics.record_error(StorageComponent.MILVUS, ConnectionError("down"))
    metrics.record_ingestion(TrackIndexStatus.READY, 40.0)
    metrics.record_ingestion(TrackIndexStatus.PENDING, 10.0)

    errors = metrics.errors()
    assert errors[StorageComponent.MILVUS].count == 2
    assert errors[StorageComponent.MILVUS].last_error_type == "ConnectionError"
    assert errors[StorageComponent.MILVUS].last_error_at == NOW
    assert errors[StorageComponent.MINIO].count == 0
    timings = metrics.ingestion()
    assert (timings.runs, timings.ready, timings.pending, timings.failed) == (2, 1, 1, 0)
    assert timings.max_ms == 40.0 and timings.average_ms == 25.0


def test_ingestion_failures_are_attributed_to_the_failing_component() -> None:
    harness = Harness()
    harness.minio.failures.append(ConnectionError("minio down"))
    harness.service.ingest_track(harness.request())
    harness.milvus.failures.append(TimeoutError("milvus down"))
    harness.service.ingest_track(harness.request())
    harness.service.ingest_track(harness.request(frame_width=65))

    errors = harness.service.metrics.errors()

    assert errors[StorageComponent.MINIO].count == 1
    assert errors[StorageComponent.MILVUS].count == 1
    assert errors[StorageComponent.POSTGRES].count == 0
    timings = harness.service.metrics.ingestion()
    assert (timings.runs, timings.pending, timings.failed) == (3, 2, 1)


def test_postgres_failure_during_registration_is_attributed_to_postgres() -> None:
    harness = Harness()
    harness.database.commit_failures[1] = ConnectionError("db down")

    with pytest.raises(ConnectionError):
        harness.service.ingest_track(harness.request())

    assert harness.service.metrics.errors()[StorageComponent.POSTGRES].count == 1


def test_imagery_records_minio_outage_but_not_missing_frames() -> None:
    harness = Harness()
    metrics = StorageMetrics()
    operator = uuid.uuid4()
    harness.database.users[operator] = SimpleNamespace(
        id=operator,
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
        assigned_area_id=harness.area_id,
    )
    harness.database.cameras[harness.camera_id].id = harness.camera_id
    harness.database.areas[harness.area_id] = SimpleNamespace(id=harness.area_id, name="A")
    request = harness.request()
    harness.service.ingest_track(request)
    frames = SimpleNamespace(get_frame=lambda key: (_ for _ in ()).throw(TimeoutError()))
    service = TrackImageService(
        lambda: FakeUnitOfWork(harness.database),  # type: ignore[arg-type,return-value]
        frames,  # type: ignore[arg-type]
        storage_metrics=metrics,
    )

    with pytest.raises(TimeoutError):
        service.search_result_image(operator, request.track_id, ImageVariant.PERSON_CROP)

    assert metrics.errors()[StorageComponent.MINIO].count == 1


class StatusWorld:
    def __init__(self) -> None:
        self.harness = Harness()
        self.admin = uuid.uuid4()
        self.harness.database.users[self.admin] = SimpleNamespace(
            id=self.admin, role=UserRole.ADMIN, status=UserStatus.ACTIVE
        )
        self.health = SimpleNamespace(
            check=lambda: SimpleNamespace(
                components={"postgres": {"status": "ok"}, "milvus": {"status": "error"}}
            )
        )

    def service(self, *, offset: timedelta = timedelta()) -> StorageStatusService:
        return StorageStatusService(
            lambda: FakeUnitOfWork(self.harness.database),  # type: ignore[arg-type,return-value]
            self.harness.service.metrics,
            health=self.health,  # type: ignore[arg-type]
            clock=lambda: NOW + offset,
        )


def test_status_snapshot_reports_counts_backlog_health_and_warnings() -> None:
    world = StatusWorld()
    harness = world.harness
    harness.service.ingest_track(harness.request())
    harness.milvus.failures.append(TimeoutError("down"))
    harness.service.ingest_track(harness.request())
    harness.service.ingest_track(harness.request(frame_width=65))

    status = world.service(offset=timedelta(minutes=1)).snapshot(world.admin)

    assert status.tracks_by_status == {"PENDING": 1, "READY": 1, "FAILED": 1}
    assert status.outbox_by_status["PENDING"] == 1
    assert status.outbox_by_status["DEAD"] == 1
    assert status.outbox_by_status["COMPLETED"] == 1
    assert status.oldest_due_outbox_age_seconds == pytest.approx(58.0)
    assert status.component_errors["milvus"].count == 1
    assert status.component_health == {"postgres": "ok", "milvus": "error"}
    assert set(status.warnings) == {"dead_outbox_events", "failed_tracks", "milvus_unhealthy"}
    assert status.ingestion.runs == 3


def test_status_snapshot_is_admin_only() -> None:
    world = StatusWorld()
    operator = uuid.uuid4()
    world.harness.database.users[operator] = SimpleNamespace(
        id=operator, role=UserRole.OPERATOR, status=UserStatus.ACTIVE
    )

    for actor in (operator, uuid.uuid4()):
        with pytest.raises(StatusAccessDeniedError):
            world.service().snapshot(actor)
