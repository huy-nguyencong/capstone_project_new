"""Integration coverage for STO-06 and STO-07."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.exc import DBAPIError

from person_search.auth.passwords import PasswordHasher
from person_search.config import PostgresSettings
from person_search.storage.postgres.seed import seed_development_users, seed_reference_data

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set migration integration flag with a disposable database",
    ),
]


def test_case_rules_populated_migration_indexes_and_seed() -> None:
    settings = PostgresSettings.from_environment(os.environ)
    engine = sa.create_engine(settings.dsn)
    config = Config("alembic.ini")
    keys = {
        name: uuid.uuid4()
        for name in (
            "area",
            "camera",
            "operator",
            "viewer",
            "config",
            "job",
            "track",
            "case",
            "result_a",
            "result_b",
            "audit",
        )
    }
    now = datetime.now(UTC)

    command.downgrade(config, "base")
    command.upgrade(config, "20260925_0003")
    try:
        assert seed_reference_data(os.environ) == 2
        assert seed_reference_data(os.environ) == 0
        assert seed_development_users(os.environ) == 3
        assert seed_development_users(os.environ) == 0
        with engine.connect() as connection:
            seeded_users = connection.execute(
                sa.text(
                    "SELECT username, password_hash, role, assigned_area_id "
                    "FROM users WHERE username IN ('admin', 'operator', 'viewer') "
                    "ORDER BY username"
                )
            ).all()
        assert [row.username for row in seeded_users] == ["admin", "operator", "viewer"]
        assert [row.role for row in seeded_users] == ["ADMIN", "OPERATOR", "VIEWER"]
        assert seeded_users[1].assigned_area_id is not None
        assert seeded_users[0].assigned_area_id is None
        assert seeded_users[2].assigned_area_id is None
        assert all(PasswordHasher().verify(row.password_hash, "password") for row in seeded_users)
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO areas (id, code, name) VALUES (:id, 'AREA-X', 'Area X')"),
                {"id": keys["area"]},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, username, password_hash, display_name, role, assigned_area_id) VALUES "
                    "(:operator, 'operator-x', 'hash', 'Operator', 'OPERATOR', :area), "
                    "(:viewer, 'viewer-x', 'hash', 'Viewer', 'VIEWER', NULL)"
                ),
                keys,
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cameras (id, area_id, code, name) "
                    "VALUES (:camera, :area, 'CAM-X', 'Camera snapshot')"
                ),
                keys,
            )
            connection.execute(
                sa.text(
                    "INSERT INTO ai_config_versions "
                    "(id, version, detector_name, detector_version, tracker_name, "
                    "tracker_version, encoder_name, encoder_version, encoder_dimension, "
                    "checkpoint_sha256) VALUES "
                    "(:config, 'pipeline-x', 'detector', '1', 'tracker', '1', "
                    "'encoder', '1', 256, :sha)"
                ),
                {**keys, "sha": "a" * 64},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO processing_jobs "
                    "(id, camera_id, ai_config_version_id, source_type, source_ref, "
                    "sampling_interval, timeline_origin_utc) VALUES "
                    "(:job, :camera, :config, 'FILE', 'clip.mp4', 5, :now)"
                ),
                {**keys, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO person_tracks "
                    "(id, camera_id, processing_job_id, ai_config_version_id, appeared_at_utc, "
                    "source_started_at_ms, source_ended_at_ms, representative_frame_timestamp_ms, "
                    "bbox_x, bbox_y, bbox_width, bbox_height, frame_width, frame_height, "
                    "encoder_version) VALUES "
                    "(:track, :camera, :job, :config, :now, 0, 1000, 500, 10, 10, "
                    "100, 200, 1920, 1080, '1')"
                ),
                {**keys, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cases (id, owner_user_id, title) "
                    "VALUES (:case, :operator, 'Investigation')"
                ),
                keys,
            )

        with pytest.raises(DBAPIError, match="owner must be an Operator"):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO cases (id, owner_user_id, title) "
                        "VALUES (:id, :viewer, 'Invalid')"
                    ),
                    {**keys, "id": uuid.uuid4()},
                )

        result_sql = sa.text(
            "INSERT INTO case_results "
            "(id, case_id, track_id, camera_name_snapshot, area_name_snapshot, "
            "appeared_at_snapshot) VALUES "
            "(:id, :case, :track, 'Camera snapshot', 'Area X', :now)"
        )
        with engine.begin() as connection:
            connection.execute(result_sql, {**keys, "id": keys["result_a"], "now": now})
            connection.execute(result_sql, {**keys, "id": keys["result_b"], "now": now})
            connection.execute(
                sa.text("DELETE FROM case_results WHERE id = :id"), {"id": keys["result_a"]}
            )
            assert (
                connection.scalar(
                    sa.text("SELECT count(*) FROM case_results WHERE case_id = :case"), keys
                )
                == 1
            )
            assert (
                connection.scalar(
                    sa.text("SELECT count(*) FROM person_tracks WHERE id = :track"), keys
                )
                == 1
            )
            connection.execute(
                sa.text("UPDATE users SET status = 'LOCKED' WHERE id = :operator"), keys
            )
            assert (
                connection.scalar(sa.text("SELECT count(*) FROM cases WHERE id = :case"), keys) == 1
            )
            connection.execute(
                sa.text(
                    "INSERT INTO audit_logs "
                    "(id, actor_user_id, event_type, target_type, target_id, result) "
                    "VALUES (:audit, :operator, 'CASE_VIEW', 'CASE', :case, 'SUCCESS')"
                ),
                keys,
            )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM audit_logs WHERE id = :audit"), keys)

        command.upgrade(config, "head")
        command.check(config)
        indexes = {item["name"] for item in sa.inspect(engine).get_indexes("person_tracks")}
        assert {
            "ix_person_tracks_camera_appeared_at",
            "ix_person_tracks_index_status",
            "ix_person_tracks_ready_camera_appeared_at",
        } <= indexes
        with engine.begin() as connection:
            connection.execute(sa.text("SET LOCAL enable_seqscan = off"))
            plan = " ".join(
                row[0]
                for row in connection.execute(
                    sa.text(
                        "EXPLAIN SELECT id FROM person_tracks "
                        "WHERE camera_id = :camera AND index_status = 'READY' "
                        "ORDER BY appeared_at_utc"
                    ),
                    keys,
                )
            )
            assert "ix_person_tracks_ready_camera_appeared_at" in plan

        command.downgrade(config, "20260925_0003")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
        command.downgrade(config, "base")
