from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from e2e_stack import StorageStack, step, unit_vector
from pymilvus import MilvusException

from person_search.services.audit import AuditRecorder
from person_search.services.cases import CaseListQuery, CaseService
from person_search.services.storage_maintenance import OutboxRetryWorker, StorageReconciler
from person_search.services.storage_status import (
    StorageComponent,
    StorageMetrics,
    StorageStatusService,
)
from person_search.services.track_imagery import (
    ImageVariant,
    TrackImageNotFoundError,
    TrackImageService,
)
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.track_search import (
    CameraOutOfScopeError,
    TrackSearchQuery,
    TrackSearchService,
)
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import TrackIndexStatus

pytestmark = pytest.mark.e2e


class UnavailableMilvusClient:
    def __getattr__(self, name: str) -> Any:
        def fail(*args: object, **kwargs: object) -> Any:
            raise MilvusException(code=2, message="Fail connecting to server on 127.0.0.1:1")

        return fail


def _search_ids(search: TrackSearchService, actor: Any, **options: Any) -> list[Any]:
    query = TrackSearchQuery(unit_vector(0), top_k=options.pop("top_k", 8), **options)
    return [result.track_id for result in search.search(actor, query)]


def test_track_to_search_to_image_to_case_to_viewer(storage_stack: StorageStack) -> None:
    stack = storage_stack
    ids = stack.ids
    metrics = StorageMetrics()
    ingestion = TrackIngestionService(
        stack.unit_of_work, stack.frames, stack.index, metrics=metrics
    )
    search = TrackSearchService(stack.unit_of_work, stack.index, storage_metrics=metrics)
    imagery = TrackImageService(stack.unit_of_work, stack.frames, storage_metrics=metrics)
    cases = CaseService(stack.unit_of_work, audit=AuditRecorder(stack.unit_of_work))

    track_a = stack.request("a", vector=unit_vector(0))
    track_b = stack.request("b", vector=unit_vector(0), color=(0, 0, 160))

    with step("ingest READY tracks into PostgreSQL, MinIO and Milvus", "ingestion"):
        assert ingestion.ingest_track(track_a).status is TrackIndexStatus.READY
        assert ingestion.ingest_track(track_b).status is TrackIndexStatus.READY
    with step("verify full frame stored with checksum", "minio"):
        with stack.unit_of_work() as work:
            assert work.repositories is not None
            stored = work.repositories.tracks.get(track_a.track_id)
            assert stored is not None and stored.minio_object_key is not None
            key = stored.minio_object_key
        assert stack.frames.head_frame(key).checksum_sha256 == track_a.frame_sha256
    with step("verify vector stored with scalar metadata", "milvus"):
        row = stack.index.get(track_a.track_id)
        assert row is not None and row["area_id"] == str(ids["area_a"])

    with step("search stays inside each Operator's area", "search"):
        assert _search_ids(search, ids["operator_a"]) == [track_a.track_id]
        assert _search_ids(search, ids["operator_b"]) == [track_b.track_id]
        with pytest.raises(CameraOutOfScopeError):
            _search_ids(search, ids["operator_a"], camera_ids=(ids["camera_b"],))

    with step("authorized crop and full frame", "imagery"):
        crop = imagery.search_result_image(
            ids["operator_a"], track_a.track_id, ImageVariant.PERSON_CROP
        )
        frame = imagery.search_result_image(
            ids["operator_a"], track_a.track_id, ImageVariant.FULL_FRAME
        )
        assert (crop.width, crop.height) == (24, 48)
        assert (frame.width, frame.height) == (96, 64)
        with pytest.raises(TrackImageNotFoundError):
            imagery.search_result_image(
                ids["operator_a"], track_b.track_id, ImageVariant.PERSON_CROP
            )

    with step("save the same track twice into a Case", "cases"):
        created = cases.create_case(ids["operator_a"], title="E2E case", track_id=track_a.track_id)
        case_id = created.case.id
        cases.add_result(ids["operator_a"], case_id, track_a.track_id)
        detail = cases.get_case(ids["operator_a"], case_id)
        assert [result.track_id for result in detail.results] == [track_a.track_id] * 2
        first_result_id = detail.results[0].id

    with step("optimistic Case updates survive the updated_at trigger", "cases"):
        renamed = cases.update_case(
            ids["operator_a"],
            case_id,
            title="E2E case renamed",
            expected_updated_at=detail.case.updated_at,
        )
        noted = cases.update_case(
            ids["operator_a"], case_id, note="second edit", expected_updated_at=renamed.updated_at
        )
        assert noted.title == "E2E case renamed" and noted.note == "second edit"

    with step("Operator area change: new searches move, old Case stays", "authorization"):
        stack.execute(
            "UPDATE users SET assigned_area_id = :area WHERE id = :id",
            area=ids["area_b"],
            id=ids["operator_a"],
        )
        assert _search_ids(search, ids["operator_a"]) == [track_b.track_id]
        assert len(cases.get_case(ids["operator_a"], case_id).results) == 2
        case_crop = imagery.case_result_image(
            ids["operator_a"], first_result_id, ImageVariant.PERSON_CROP
        )
        assert (case_crop.width, case_crop.height) == (24, 48)
        with pytest.raises(TrackImageNotFoundError):
            imagery.search_result_image(
                ids["operator_a"], track_a.track_id, ImageVariant.PERSON_CROP
            )

    with step("Viewer reads the Case and dashboard counts two results", "cases"):
        viewer_detail = cases.get_case(ids["viewer"], case_id)
        assert len(viewer_detail.results) == 2
        assert [item.id for item in cases.list_cases(ids["viewer"], CaseListQuery()).items] == [
            case_id
        ]
        dashboard = cases.viewer_dashboard(ids["viewer"])
        assert (dashboard.total_cases, dashboard.total_case_results) == (1, 2)
        viewer_image = imagery.case_result_image(
            ids["viewer"], first_result_id, ImageVariant.FULL_FRAME
        )
        assert viewer_image.cache_control == "private, no-store"

    with step("MinIO outage keeps the track PENDING until the producer retries", "minio"):
        unreachable = MinioStorage(
            dataclasses.replace(stack.minio_settings, endpoint="127.0.0.1:1", timeout_seconds=1)
        )
        broken_frames = MinioFrameStore(unreachable.client, stack.minio_settings.bucket)
        broken_ingestion = TrackIngestionService(
            stack.unit_of_work, broken_frames, stack.index, metrics=metrics
        )
        minio_track = stack.request("b", vector=unit_vector(0), started_at_ms=5_000)
        result = broken_ingestion.ingest_track(minio_track)
        assert result.status is TrackIndexStatus.PENDING and result.retryable
        assert metrics.errors()[StorageComponent.MINIO].count >= 1
        assert minio_track.track_id not in _search_ids(search, ids["operator_b"])
        assert ingestion.ingest_track(minio_track).status is TrackIndexStatus.READY
        assert minio_track.track_id in _search_ids(search, ids["operator_b"])
        unreachable.close()

    with step("Milvus outage keeps the track PENDING until the outbox worker", "milvus"):
        broken_index = MilvusPersonTrackIndex(
            UnavailableMilvusClient(),
            encoder_version=stack.encoder_version,
            dimension=stack.index.dimension,
        )
        milvus_ingestion = TrackIngestionService(
            stack.unit_of_work, stack.frames, broken_index, metrics=metrics
        )
        milvus_track = stack.request("b", vector=unit_vector(0), started_at_ms=9_000)
        result = milvus_ingestion.ingest_track(milvus_track)
        assert result.status is TrackIndexStatus.PENDING and result.retryable
        assert metrics.errors()[StorageComponent.MILVUS].count >= 1
        assert milvus_track.track_id not in _search_ids(search, ids["operator_b"])
        worker = OutboxRetryWorker(
            stack.unit_of_work,
            ingestion,
            clock=lambda: datetime.now(UTC) + timedelta(minutes=5),
        )
        summary = worker.run_once()
        assert summary.ready == 1 and summary.errors == 0
        assert milvus_track.track_id in _search_ids(search, ids["operator_b"])

    with step("reconciliation finds no missing artifacts", "reconciliation"):
        report = StorageReconciler(
            stack.unit_of_work,
            stack.frames,
            stack.index,
            frame_prefix=f"tracks/v1/{ids['camera_b']}",
        ).run()
        assert report.missing_objects == []
        assert report.missing_vectors == []
        assert report.checksum_mismatches == []
        assert report.orphan_vectors == []

    with step("Admin status reports counts and component errors", "status"):
        status = StorageStatusService(stack.unit_of_work, metrics).snapshot(ids["admin"])
        assert status.tracks_by_status["READY"] == 4
        assert status.tracks_by_status["PENDING"] == 0
        assert status.component_errors["minio"].count >= 1
        assert status.component_errors["milvus"].count >= 1
