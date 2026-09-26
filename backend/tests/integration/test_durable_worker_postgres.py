from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from person_search.workers.durable import PostgresWorkerLock

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PERSON_SEARCH_CAMERA_TEST_DSN"),
        reason="requires disposable database",
    ),
]


def test_two_workers_cannot_hold_the_global_lock_concurrently():
    engine = create_engine(os.environ["PERSON_SEARCH_CAMERA_TEST_DSN"])
    try:
        with PostgresWorkerLock(engine) as first:
            assert first is True
            with PostgresWorkerLock(engine) as second:
                assert second is False
        with PostgresWorkerLock(engine) as recovered:
            assert recovered is True
    finally:
        engine.dispose()


def test_job_progress_migration_and_constraint_are_active():
    engine = create_engine(os.environ["PERSON_SEARCH_CAMERA_TEST_DSN"])
    try:
        with engine.connect() as connection:
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'processing_jobs'"
                    )
                ).scalars()
            )
            constraints = set(
                connection.execute(
                    text(
                        "SELECT constraint_name FROM information_schema.table_constraints "
                        "WHERE table_name = 'processing_jobs'"
                    )
                ).scalars()
            )
        assert {"completed_tracks", "published_tracks"} <= columns
        assert "ck_jobs_track_progress" in constraints
    finally:
        engine.dispose()
