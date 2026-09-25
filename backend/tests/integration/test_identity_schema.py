"""Migration and database constraint tests for STO-04."""

from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from person_search.config import PostgresSettings
from person_search.storage.postgres.models import Camera, ImmutableFieldError

load_dotenv()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set PERSON_SEARCH_RUN_MIGRATION_INTEGRATION=1 with a disposable database",
    ),
]


def _alembic_config() -> Config:
    return Config("alembic.ini")


def test_migration_constraints_and_round_trip() -> None:
    settings = PostgresSettings.from_environment(os.environ)
    engine = sa.create_engine(settings.dsn)
    migration_config = _alembic_config()

    area_a = uuid.uuid4()
    area_b = uuid.uuid4()
    operator_id = uuid.uuid4()
    camera_id = uuid.uuid4()

    command.downgrade(migration_config, "base")
    command.upgrade(migration_config, "head")
    try:
        command.check(migration_config)
        inspector = sa.inspect(engine)
        assert {"alembic_version", "areas", "users", "cameras"} <= set(
            inspector.get_table_names()
        )

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO areas (id, code, name) VALUES "
                    "(:area_a, 'AREA-A', 'Area A'), (:area_b, 'AREA-B', 'Area B')"
                ),
                {"area_a": area_a, "area_b": area_b},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, username, password_hash, display_name, role, assigned_area_id) "
                    "VALUES (:id, 'operator-a', 'hash', 'Operator A', 'OPERATOR', :area_id)"
                ),
                {"id": operator_id, "area_id": area_a},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cameras (id, area_id, code, name) "
                    "VALUES (:id, :area_id, 'CAM-01', 'Camera 1')"
                ),
                {"id": camera_id, "area_id": area_a},
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, password_hash, display_name, role) "
                        "VALUES (:id, 'operator-no-area', 'hash', 'Invalid', 'OPERATOR')"
                    ),
                    {"id": uuid.uuid4()},
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, password_hash, display_name, role, assigned_area_id) "
                        "VALUES (:id, 'admin-with-area', 'hash', 'Invalid', 'ADMIN', :area_id)"
                    ),
                    {"id": uuid.uuid4(), "area_id": area_a},
                )

        with engine.begin() as connection:
            version = connection.scalar(
                sa.text("SELECT version FROM users WHERE id = :id"),
                {"id": operator_id},
            )
            assert version == 1

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE users SET version = 0 WHERE id = :id"),
                    {"id": operator_id},
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO cameras (id, area_id, code, name) "
                        "VALUES (:id, NULL, 'CAM-NO-AREA', 'Invalid')"
                    ),
                    {"id": uuid.uuid4()},
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO cameras (id, area_id, code, name, rtsp_url) "
                        "VALUES (:id, :area_id, 'CAM-SECRET', 'Invalid', "
                        "'rtsp://user:password@camera/stream')"
                    ),
                    {"id": uuid.uuid4(), "area_id": area_a},
                )

        with pytest.raises(DBAPIError, match="Camera.area_id is immutable"):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE cameras SET area_id = :area_b WHERE id = :camera_id"),
                    {"area_b": area_b, "camera_id": camera_id},
                )

        with pytest.raises(DBAPIError, match="Area.code is immutable"):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE areas SET code = 'AREA-RENAMED' WHERE id = :area_id"),
                    {"area_id": area_a},
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("DELETE FROM areas WHERE id = :area_id"),
                    {"area_id": area_a},
                )

        with Session(engine) as session:
            camera = session.get(Camera, camera_id)
            assert camera is not None
            camera.area_id = area_b
            with pytest.raises(ImmutableFieldError, match="Camera.area_id"):
                session.flush()
            session.rollback()

        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE users SET status = 'INACTIVE' WHERE id = :id"),
                {"id": operator_id},
            )
            connection.execute(
                sa.text("UPDATE cameras SET status = 'INACTIVE' WHERE id = :id"),
                {"id": camera_id},
            )
            user_area = connection.scalar(
                sa.text("SELECT assigned_area_id FROM users WHERE id = :id"),
                {"id": operator_id},
            )
            camera_area = connection.scalar(
                sa.text("SELECT area_id FROM cameras WHERE id = :id"),
                {"id": camera_id},
            )
            assert user_area == area_a
            assert camera_area == area_a
    finally:
        engine.dispose()
        command.downgrade(migration_config, "base")

    verification_engine = sa.create_engine(settings.dsn)
    try:
        remaining_tables = set(sa.inspect(verification_engine).get_table_names())
        assert not {"areas", "users", "cameras"} & remaining_tables
    finally:
        verification_engine.dispose()
