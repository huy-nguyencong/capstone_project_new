"""Real PostgreSQL integration coverage for STO-15 and STO-16."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

from person_search.config import PostgresSettings
from person_search.services.audit import AuditEvent, AuditLogQuery, AuditLogService, AuditRecorder
from person_search.services.cases import CaseAccessDeniedError, CaseService
from person_search.services.storage_status import (
    StorageComponent,
    StorageMetrics,
    StorageStatusService,
)
from person_search.storage.postgres.models import AuditResult, TrackIndexStatus
from person_search.storage.postgres.unit_of_work import UnitOfWork

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set migration integration flag with a disposable database",
    ),
]


def test_case_audit_dashboard_and_storage_status_services() -> None:
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Config("alembic.ini")
    now = datetime.now(UTC).replace(microsecond=0)
    ids = {
        name: uuid.uuid4()
        for name in (
            "area_a",
            "area_b",
            "camera",
            "operator",
            "viewer",
            "admin",
            "config",
            "job",
            "track",
        )
    }

    def unit_of_work() -> UnitOfWork:
        return UnitOfWork(factory)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO areas (id, code, name) VALUES "
                    "(:area_a, 'AREA-SA', 'Area A'), (:area_b, 'AREA-SB', 'Area B')"
                ),
                ids,
            )
            connection.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, username, password_hash, display_name, role, assigned_area_id) VALUES "
                    "(:operator, 'operator-services', 'hash', 'Operator', 'OPERATOR', :area_a), "
                    "(:viewer, 'viewer-services', 'hash', 'Viewer', 'VIEWER', NULL), "
                    "(:admin, 'admin-services', 'hash', 'Admin', 'ADMIN', NULL)"
                ),
                ids,
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cameras (id, area_id, code, name) "
                    "VALUES (:camera, :area_a, 'CAM-SA', 'Camera A')"
                ),
                ids,
            )
            connection.execute(
                sa.text(
                    "INSERT INTO ai_config_versions "
                    "(id, version, detector_name, detector_version, tracker_name, "
                    "tracker_version, encoder_name, encoder_version, encoder_dimension, "
                    "checkpoint_sha256) VALUES "
                    "(:config, 'pipeline-services', 'detector', '1', 'tracker', '1', "
                    "'encoder', 'encoder_services', 4, :sha)"
                ),
                {**ids, "sha": "a" * 64},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO processing_jobs "
                    "(id, camera_id, ai_config_version_id, source_type, source_ref, "
                    "sampling_interval, timeline_origin_utc) VALUES "
                    "(:job, :camera, :config, 'FILE', 'clip.mp4', 1, :now)"
                ),
                {**ids, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO person_tracks "
                    "(id, camera_id, processing_job_id, ai_config_version_id, appeared_at_utc, "
                    "source_started_at_ms, source_ended_at_ms, representative_frame_timestamp_ms, "
                    "bbox_x, bbox_y, bbox_width, bbox_height, frame_width, frame_height, "
                    "encoder_version) VALUES "
                    "(:track, :camera, :job, :config, :now, 0, 1000, 500, "
                    "1, 2, 10, 20, 64, 48, 'encoder_services')"
                ),
                {**ids, "now": now},
            )
            connection.execute(
                sa.text(
                    "UPDATE person_tracks SET index_status = 'READY', "
                    "minio_object_key = 'tracks/v1/frame.jpg', frame_sha256 = :sha, "
                    "frame_size_bytes = 100, vector_indexed_at = :now WHERE id = :track"
                ),
                {**ids, "sha": "b" * 64, "now": now},
            )

        cases = CaseService(unit_of_work, audit=AuditRecorder(unit_of_work), clock=lambda: now)
        detail = cases.create_case(ids["operator"], title="Case", track_id=ids["track"])
        duplicate = cases.add_result(ids["operator"], detail.case.id, ids["track"])
        assert duplicate.id != detail.results[0].id
        assert len(cases.get_case(ids["viewer"], detail.case.id).results) == 2

        with pytest.raises(CaseAccessDeniedError):
            cases.add_result(ids["viewer"], detail.case.id, ids["track"])

        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE users SET assigned_area_id = :area_b WHERE id = :operator"), ids
            )
        assert cases.get_case(ids["operator"], detail.case.id).case.id == detail.case.id
        dashboard = cases.viewer_dashboard(ids["viewer"])
        assert dashboard.total_cases == 1
        assert dashboard.total_case_results == 2

        audit_page = AuditLogService(unit_of_work).list(
            ids["admin"], AuditLogQuery(event_types=(AuditEvent.CASE_RESULT_ADDED,))
        )
        assert [item.result for item in audit_page.items] == [
            AuditResult.FAILURE,
            AuditResult.SUCCESS,
        ]
        success = next(item for item in audit_page.items if item.result is AuditResult.SUCCESS)
        assert success.metadata["track_id"] == str(ids["track"])

        metrics = StorageMetrics(clock=lambda: now)
        metrics.record_error(StorageComponent.MINIO, TimeoutError("secret must not leak"))
        metrics.record_ingestion(TrackIndexStatus.READY, 25.0)
        health = SimpleNamespace(
            check=lambda: SimpleNamespace(
                components={
                    "postgres": {"status": "ok"},
                    "milvus": {"status": "ok"},
                    "minio": {"status": "error"},
                }
            )
        )
        status = StorageStatusService(
            unit_of_work, metrics, health=health, clock=lambda: now
        ).snapshot(ids["admin"])
        assert status.tracks_by_status["READY"] == 1
        assert status.component_errors["minio"].count == 1
        assert status.component_errors["minio"].last_error_type == "TimeoutError"
        assert "minio_unhealthy" in status.warnings
    finally:
        engine.dispose()
        command.downgrade(config, "base")
