"""Migration and database constraint tests for STO-05."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.exc import DBAPIError, IntegrityError

from person_search.config import PostgresSettings

load_dotenv()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set PERSON_SEARCH_RUN_MIGRATION_INTEGRATION=1 with a disposable database",
    ),
]


def test_processing_schema_constraints_and_round_trip() -> None:
    settings = PostgresSettings.from_environment(os.environ)
    engine = sa.create_engine(settings.dsn)
    config = Config("alembic.ini")
    ids = {name: uuid.uuid4() for name in ("area", "camera", "config", "job", "track")}
    now = datetime.now(UTC)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        command.check(config)
        inspector = sa.inspect(engine)
        expected = {
            "ai_config_versions",
            "processing_jobs",
            "person_tracks",
            "storage_outbox_events",
        }
        assert expected <= set(inspector.get_table_names())
        assert "matching_score" not in {
            column["name"] for column in inspector.get_columns("person_tracks")
        }

        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO areas (id, code, name) VALUES (:id, 'AREA-A', 'Area A')"),
                {"id": ids["area"]},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cameras (id, area_id, code, name) "
                    "VALUES (:id, :area_id, 'CAM-01', 'Camera 1')"
                ),
                {"id": ids["camera"], "area_id": ids["area"]},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO ai_config_versions "
                    "(id, version, detector_name, detector_version, tracker_name, "
                    "tracker_version, encoder_name, encoder_version, encoder_dimension, "
                    "checkpoint_sha256, status) VALUES "
                    "(:id, 'pipeline-1', 'yolo', '1', 'bytetrack', '1', 'reid', '1', "
                    "512, :sha, 'ACTIVE')"
                ),
                {"id": ids["config"], "sha": "a" * 64},
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

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO processing_jobs "
                        "(id, camera_id, ai_config_version_id, source_type, source_ref, "
                        "sampling_interval, timeline_origin_utc) VALUES "
                        "(:id, :camera, :config, 'FILE', 'bad.mp4', 0, :now)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "camera": ids["camera"],
                        "config": ids["config"],
                        "now": now,
                    },
                )

        track_sql = sa.text(
            "INSERT INTO person_tracks "
            "(id, camera_id, processing_job_id, ai_config_version_id, appeared_at_utc, "
            "source_started_at_ms, source_ended_at_ms, representative_frame_timestamp_ms, "
            "bbox_x, bbox_y, bbox_width, bbox_height, frame_width, frame_height, "
            "encoder_version, index_status) VALUES "
            "(:id, :camera, :job, :config, :now, 0, 1000, 500, 10, 20, :width, 200, "
            "1920, 1080, '1', :status)"
        )
        params = {
            **ids,
            "id": ids["track"],
            "now": now,
            "width": 100,
            "status": "PENDING",
        }
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(track_sql, {**params, "id": uuid.uuid4(), "width": 2_000})
        with pytest.raises(DBAPIError, match="must be created as PENDING"):
            with engine.begin() as connection:
                connection.execute(track_sql, {**params, "id": uuid.uuid4(), "status": "READY"})

        with engine.begin() as connection:
            connection.execute(track_sql, params)
            connection.execute(
                sa.text(
                    "INSERT INTO storage_outbox_events "
                    "(id, track_id, event_type, payload, available_at) "
                    "VALUES (:id, :track, 'INDEX_VECTOR', CAST(:payload AS jsonb), :now)"
                ),
                {"id": uuid.uuid4(), "track": ids["track"], "payload": "{}", "now": now},
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE person_tracks SET index_status = 'READY' WHERE id = :id"),
                    {"id": ids["track"]},
                )

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE person_tracks SET index_status = 'READY', "
                    "minio_object_key = 'tracks/frame.jpg', frame_sha256 = :sha, "
                    "frame_size_bytes = 123, vector_indexed_at = :now WHERE id = :id"
                ),
                {"id": ids["track"], "sha": "b" * 64, "now": now},
            )
        with pytest.raises(DBAPIError, match="Invalid PersonTrack"):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE person_tracks SET index_status = 'PENDING' WHERE id = :id"),
                    {"id": ids["track"]},
                )
        # 20260926_0011: reconciliation may quarantine a corrupt READY track.
        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE person_tracks SET index_status = 'FAILED' WHERE id = :id"),
                {"id": ids["track"]},
            )
    finally:
        engine.dispose()
        command.downgrade(config, "20260925_0001")

    verification_engine = sa.create_engine(settings.dsn)
    try:
        remaining = set(sa.inspect(verification_engine).get_table_names())
        assert not expected & remaining
        assert {"areas", "users", "cameras"} <= remaining
    finally:
        verification_engine.dispose()
        command.downgrade(config, "base")
