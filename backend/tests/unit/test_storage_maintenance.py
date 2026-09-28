from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from ingestion_harness import NOW, Harness, jpeg_frame
from storage_fakes import FakeUnitOfWork

from person_search.services.storage_maintenance import (
    OutboxRetryWorker,
    StorageReconciler,
    StorageReindexer,
    track_id_from_frame_key,
)
from person_search.services.track_ingestion import (
    RetryPolicy,
    TrackIngestionError,
    TrackIngestionService,
)
from person_search.storage.contracts import RASA_EMBEDDING_DIMENSION, RASA_ENCODER_VERSION
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import OutboxStatus, TrackIndexStatus

pytestmark = pytest.mark.unit


def _service_at(harness: Harness, now_offset: timedelta) -> TrackIngestionService:
    return TrackIngestionService(
        lambda: FakeUnitOfWork(harness.database),  # type: ignore[arg-type,return-value]
        MinioFrameStore(harness.minio, "frames"),
        MilvusPersonTrackIndex(
            harness.milvus, encoder_version=RASA_ENCODER_VERSION, dimension=RASA_EMBEDDING_DIMENSION
        ),
        retry_policy=RetryPolicy(max_attempts=3),
        clock=lambda: NOW + now_offset,
    )


def _worker(harness: Harness, now_offset: timedelta) -> OutboxRetryWorker:
    return OutboxRetryWorker(
        lambda: FakeUnitOfWork(harness.database),  # type: ignore[arg-type,return-value]
        _service_at(harness, now_offset),
        clock=lambda: NOW + now_offset,
    )


def _reconciler(harness: Harness) -> StorageReconciler:
    return StorageReconciler(
        lambda: FakeUnitOfWork(harness.database),  # type: ignore[arg-type,return-value]
        MinioFrameStore(harness.minio, "frames"),
        MilvusPersonTrackIndex(
            harness.milvus, encoder_version=RASA_ENCODER_VERSION, dimension=RASA_EMBEDDING_DIMENSION
        ),
        stale_after=timedelta(minutes=30),
        batch_size=2,
        clock=lambda: NOW,
    )


def test_worker_waits_for_backoff_then_publishes_pending_track() -> None:
    harness = Harness()
    request = harness.request()
    harness.milvus.failures.append(TimeoutError("milvus down"))
    harness.service.ingest_track(request)

    early = _worker(harness, timedelta(seconds=1)).run_once()
    summary = _worker(harness, timedelta(seconds=3)).run_once()

    assert early.claimed == 0
    assert summary.claimed == 1 and summary.ready == 1
    harness.assert_converged(request)
    assert harness.milvus.upserts == 1
    assert harness.minio.puts == 1


def test_worker_recovers_event_locked_by_crashed_process() -> None:
    harness = Harness()
    crashed, running = harness.request(), harness.request()
    harness.milvus.failures.extend([TimeoutError("down"), TimeoutError("down")])
    harness.service.ingest_track(crashed)
    harness.service.ingest_track(running)
    harness.event(crashed.track_id).status = OutboxStatus.PROCESSING
    harness.event(crashed.track_id).locked_at = NOW - timedelta(minutes=10)
    harness.event(running.track_id).status = OutboxStatus.PROCESSING
    harness.event(running.track_id).locked_at = NOW

    summary = _worker(harness, timedelta(minutes=1)).run_once()

    assert summary.claimed == 1 and summary.ready == 1
    assert harness.database.tracks[crashed.track_id].index_status is TrackIndexStatus.READY
    assert harness.database.tracks[running.track_id].index_status is TrackIndexStatus.PENDING


def test_missing_frame_is_retried_then_dead_lettered() -> None:
    harness = Harness()
    request = harness.request()
    harness.minio.failures.append(ConnectionError("minio down"))
    harness.service.ingest_track(request)

    for offset in (timedelta(minutes=1), timedelta(minutes=2)):
        _worker(harness, offset).run_once()

    track = harness.database.tracks[request.track_id]
    event = harness.event(request.track_id)
    assert track.index_status is TrackIndexStatus.FAILED
    assert track.failure_code == "FRAME_VERIFY_FAILED"
    assert event.status is OutboxStatus.DEAD
    assert event.attempts == 3
    assert harness.milvus.rows == {}


def test_producer_resend_after_frame_failure_converges_with_worker() -> None:
    harness = Harness()
    request = harness.request()
    harness.minio.failures.append(ConnectionError("minio down"))
    harness.service.ingest_track(request)

    assert harness.service.ingest_track(request).status is TrackIndexStatus.READY
    summary = _worker(harness, timedelta(minutes=1)).run_once()

    assert summary.claimed == 0
    harness.assert_converged(request)


def test_worker_counts_errors_and_leaves_event_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness()
    request = harness.request()
    harness.milvus.failures.append(TimeoutError("down"))
    harness.service.ingest_track(request)
    worker = _worker(harness, timedelta(minutes=1))
    monkeypatch.setattr(
        worker._ingestion, "resume", lambda track_id: (_ for _ in ()).throw(ConnectionError())
    )

    summary = worker.run_once()

    assert summary.errors == 1
    assert harness.event(request.track_id).status is OutboxStatus.PROCESSING


def test_requeue_failed_track_resets_event_and_audits() -> None:
    harness = Harness()
    request = harness.request(frame_width=65)
    harness.service.ingest_track(request)
    actor = uuid.uuid4()

    result = harness.service.requeue_failed(request.track_id, actor_user_id=actor)

    assert result.status is TrackIndexStatus.PENDING
    track = harness.database.tracks[request.track_id]
    event = harness.event(request.track_id)
    assert track.index_status is TrackIndexStatus.PENDING and track.failure_code is None
    assert event.status is OutboxStatus.PENDING and event.attempts == 0
    assert [entry.event_type for entry in harness.database.audit_logs] == [
        "storage.track_failed",
        "storage.track_requeued",
    ]
    failed_audit, requeue_audit = harness.database.audit_logs
    assert failed_audit.result.value == "FAILURE"
    assert failed_audit.event_metadata["step"] == "FRAME_UPLOAD"
    assert requeue_audit.actor_user_id == actor


def test_requeue_rejects_ready_track() -> None:
    harness = Harness()
    request = harness.request()
    harness.service.ingest_track(request)

    with pytest.raises(TrackIngestionError):
        harness.service.requeue_failed(request.track_id)


def test_frame_key_parser_rejects_foreign_keys() -> None:
    track_id = uuid.uuid4()

    assert track_id_from_frame_key(f"tracks/v1/c/2026/09/25/{track_id}/representative.jpg") == (
        track_id
    )
    assert track_id_from_frame_key("tracks/v1/readme.txt") is None


class ReconcileScenario:
    def __init__(self) -> None:
        self.harness = harness = Harness()
        self.ready = harness.request()
        harness.service.ingest_track(self.ready)

        self.broken = harness.request()
        harness.service.ingest_track(self.broken)
        broken_track = harness.database.tracks[self.broken.track_id]
        assert broken_track.minio_object_key is not None
        harness.minio.objects.pop(broken_track.minio_object_key)
        harness.milvus.rows.pop(str(self.broken.track_id))

        self.tampered = harness.request(frame=jpeg_frame("blue"))
        harness.service.ingest_track(self.tampered)
        tampered_key = harness.database.tracks[self.tampered.track_id].minio_object_key
        assert tampered_key is not None
        data, content_type, metadata = harness.minio.objects[tampered_key]
        harness.minio.objects[tampered_key] = (data, content_type, {**metadata, "sha256": "0" * 64})

        self.stale = harness.request()
        harness.milvus.failures.append(TimeoutError("down"))
        harness.service.ingest_track(self.stale)
        harness.database.tracks[self.stale.track_id].updated_at = NOW - timedelta(hours=1)

        self.orphan_track = uuid.uuid4()
        self.orphan_key = (
            f"tracks/v1/{harness.camera_id}/2026/09/25/{self.orphan_track}/representative.jpg"
        )
        harness.minio.objects[self.orphan_key] = (b"x", "image/jpeg", {"sha256": "1" * 64})
        self.orphan_vector = uuid.uuid4()
        harness.milvus.rows[str(self.orphan_vector)] = {"track_id": str(self.orphan_vector)}
        self.case_vector = uuid.uuid4()
        harness.milvus.rows[str(self.case_vector)] = {"track_id": str(self.case_vector)}
        harness.database.case_results[uuid.uuid4()] = SimpleNamespace(
            case_id=uuid.uuid4(), track_id=self.case_vector
        )


def test_reconcile_dry_run_reports_without_changing_data() -> None:
    scenario = ReconcileScenario()
    harness = scenario.harness
    objects_before = dict(harness.minio.objects)
    vectors_before = dict(harness.milvus.rows)

    report = _reconciler(harness).run()

    assert report.dry_run is True and report.clean is False
    assert report.stale_tracks == [scenario.stale.track_id]
    assert report.missing_objects == [scenario.broken.track_id]
    assert report.missing_vectors == [scenario.broken.track_id]
    assert report.checksum_mismatches == [scenario.tampered.track_id]
    assert report.orphan_objects == [scenario.orphan_key]
    assert report.orphan_vectors == [scenario.orphan_vector]
    assert report.deleted_objects == [] and report.deleted_vectors == []
    assert harness.minio.objects == objects_before
    assert harness.milvus.rows == vectors_before
    assert harness.database.audit_logs == []


def test_reconcile_delete_mode_removes_only_orphans_and_audits() -> None:
    scenario = ReconcileScenario()
    harness = scenario.harness
    actor = uuid.uuid4()

    report = _reconciler(harness).run(delete_orphans=True, actor_user_id=actor)

    assert report.dry_run is False
    assert report.deleted_objects == [scenario.orphan_key]
    assert report.deleted_vectors == [scenario.orphan_vector]
    assert scenario.orphan_key not in harness.minio.objects
    assert str(scenario.orphan_vector) not in harness.milvus.rows
    assert str(scenario.case_vector) in harness.milvus.rows
    assert str(scenario.ready.track_id) in harness.milvus.rows
    audit = harness.database.audit_logs[-1]
    assert audit.event_type == "storage.orphans_deleted"
    assert audit.actor_user_id == actor
    assert audit.event_metadata == {"deleted_objects": 1, "deleted_vectors": 1}


def test_reconcile_quarantines_corrupt_ready_tracks_without_deleting_history() -> None:
    scenario = ReconcileScenario()
    harness = scenario.harness
    case_id = uuid.uuid4()
    harness.database.case_results[case_id] = SimpleNamespace(
        case_id=case_id, track_id=scenario.broken.track_id
    )

    report = _reconciler(harness).run(quarantine_corrupt=True)

    assert set(report.quarantined_tracks) == {
        scenario.broken.track_id,
        scenario.tampered.track_id,
    }
    broken = harness.database.tracks[scenario.broken.track_id]
    tampered = harness.database.tracks[scenario.tampered.track_id]
    assert broken.index_status is TrackIndexStatus.FAILED
    assert broken.failure_code == "RECONCILE_MISSING_OBJECT"
    assert tampered.index_status is TrackIndexStatus.FAILED
    assert tampered.failure_code == "RECONCILE_CHECKSUM_MISMATCH"
    assert harness.database.case_results[case_id].track_id == scenario.broken.track_id
    assert (
        harness.database.events[(scenario.broken.track_id, "track.ingest")].status
        is OutboxStatus.DEAD
    )


def test_reconcile_clean_storage_reports_clean() -> None:
    harness = Harness()
    harness.service.ingest_track(harness.request())

    report = _reconciler(harness).run()

    assert report.clean is True
    assert report.truncated is False


def _reindexer(harness: Harness, **options: object) -> StorageReindexer:
    return StorageReindexer(
        lambda: FakeUnitOfWork(harness.database),  # type: ignore[arg-type,return-value]
        MilvusPersonTrackIndex(
            harness.milvus, encoder_version=RASA_ENCODER_VERSION, dimension=RASA_EMBEDDING_DIMENSION
        ),
        **{"batch_size": 1, **options},  # type: ignore[arg-type]
    )


def test_reindex_rebuilds_lost_milvus_vectors_from_outbox_payloads() -> None:
    harness = Harness()
    first, second = harness.request(), harness.request()
    harness.service.ingest_track(first)
    harness.service.ingest_track(second)
    before = {key: dict(value) for key, value in harness.milvus.rows.items()}
    harness.milvus.rows.clear()

    report = _reindexer(harness).run()

    assert report.clean is True
    assert report.indexed == 2
    assert harness.milvus.rows.keys() == before.keys()
    for track_id, row in before.items():
        assert harness.milvus.rows[track_id]["embedding"] == row["embedding"]
        assert harness.milvus.rows[track_id]["area_id"] == row["area_id"]
        assert harness.milvus.rows[track_id]["appeared_at_epoch"] == row["appeared_at_epoch"]


def test_reindex_reports_missing_payloads_failures_and_unverified_rows() -> None:
    harness = Harness()
    requests = [harness.request() for _ in range(3)]
    for request in requests:
        harness.service.ingest_track(request)
    harness.milvus.rows.clear()
    harness.event(requests[0].track_id).payload = {"version": 1}
    ordered = sorted(request.track_id for request in requests[1:])
    # The batch write fails, then the per-track retry fails too.
    harness.milvus.failures.extend([TimeoutError("down"), TimeoutError("down")])

    report = _reindexer(harness).run()

    assert report.missing_payload == [requests[0].track_id]
    assert report.failed == [ordered[0]]
    assert report.indexed == 1
    assert report.clean is False


def test_reindex_writes_and_verifies_each_batch_in_one_request() -> None:
    harness = Harness()
    for _ in range(3):
        harness.service.ingest_track(harness.request())
    harness.milvus.rows.clear()
    harness.milvus.upserts = 0

    report = _reindexer(harness, batch_size=200).run()

    assert report.clean is True
    assert report.indexed == 3
    assert harness.milvus.upserts == 1


def test_reindex_retries_a_failed_batch_per_track() -> None:
    harness = Harness()
    for _ in range(2):
        harness.service.ingest_track(harness.request())
    harness.milvus.rows.clear()
    harness.milvus.failures.append(TimeoutError("transient"))

    report = _reindexer(harness, batch_size=200).run()

    assert report.clean is True
    assert report.indexed == 2
    assert len(harness.milvus.rows) == 2


def test_reindex_reports_rows_missing_after_write_as_unverified() -> None:
    harness = Harness()
    requests = [harness.request() for _ in range(2)]
    for request in requests:
        harness.service.ingest_track(request)
    harness.milvus.rows.clear()
    harness.milvus.query_misses = 1

    report = _reindexer(harness, batch_size=200).run()

    assert sorted(report.unverified) == sorted(request.track_id for request in requests)
    assert report.indexed == 0
    assert report.clean is False


def test_reindex_skips_pending_tracks_and_honours_max_items() -> None:
    harness = Harness()
    ready = harness.request()
    harness.service.ingest_track(ready)
    harness.milvus.failures.append(TimeoutError("down"))
    harness.service.ingest_track(harness.request())
    harness.service.ingest_track(harness.request())
    harness.milvus.rows.clear()

    report = _reindexer(harness, max_items=1).run()

    assert report.indexed == 1
    assert report.truncated is True
    assert list(harness.milvus.rows) != []
