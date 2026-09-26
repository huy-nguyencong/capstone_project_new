import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from test_camera_admin import world as world
from test_video_jobs import setup as setup
from test_video_jobs import upload
from test_video_jobs import video as video

from person_search.services.monitoring import MonitoringService
from person_search.storage.postgres.models import ProcessingJob, WorkerHeartbeat
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.workers.telemetry import WorkerHeartbeatReporter, WorkerRunState

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PERSON_SEARCH_CAMERA_TEST_DSN"), reason="requires disposable database"
    ),
]


class Health:
    def check(self):
        return SimpleNamespace(components={"postgres": {"status": "ok"}})


class Search:
    def active_config(self):
        return SimpleNamespace(encoder_version="fake_demo_v1")

    def gateway(self, version):
        return SimpleNamespace()


def monitoring(factory):
    return MonitoringService(
        lambda: UnitOfWork(factory), health=Health(), search=Search(), runtime=None
    )


@pytest.fixture
def worker_id(setup):
    value = f"it-{uuid.uuid4().hex[:12]}"
    yield value
    with setup.factory() as session:
        session.execute(delete(WorkerHeartbeat))
        session.commit()


def test_worker_telemetry_schema_is_migrated(setup):
    with setup.factory() as session:
        columns = set(
            session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'processing_jobs'"
                )
            ).scalars()
        )
        heartbeat_columns = set(
            session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'worker_heartbeats'"
                )
            ).scalars()
        )
    assert {"metrics", "metrics_updated_at"} <= columns
    assert {"worker_id", "state", "heartbeat_at", "rss_bytes", "cpu_percent"} <= heartbeat_columns


def test_checkpoint_persists_sanitized_metrics_and_reclaim_resets_them(setup, video):
    job_id = uuid.UUID(upload(setup, video).json["id"])
    claimed = setup.jobs.claim()
    assert claimed.id == job_id and claimed.metrics == {}

    assert setup.jobs.checkpoint(
        job_id,
        claimed.lease_token,
        50,
        5,
        1,
        0,
        metrics={
            "source_fps": 25.0,
            "detector_ms": float("nan"),
            "rtsp_url": "rtsp://admin:secret@camera/stream",
        },
    )
    view = setup.jobs.get(job_id)
    assert view["metrics"] == {"source_fps": 25.0}
    assert view["metrics_updated_at"] is not None
    assert "secret" not in str(view)

    assert setup.jobs.defer_retry(
        job_id, claimed.lease_token, "storage_unavailable", timedelta(seconds=1)
    )
    assert setup.jobs.get(job_id)["error_code"] == "storage_unavailable"
    setup.jobs.clock = lambda: datetime.now(UTC) + timedelta(minutes=1)
    reclaimed = setup.jobs.claim()
    assert reclaimed.id == job_id
    view = setup.jobs.get(job_id)
    assert view["metrics"] == {} and view["metrics_updated_at"] is None
    assert view["error_code"] is None


def test_metrics_column_rejects_non_object_json(setup, video):
    job_id = uuid.UUID(upload(setup, video).json["id"])
    with setup.factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text("UPDATE processing_jobs SET metrics = '[1]'::jsonb WHERE id = :id"),
                {"id": job_id},
            )
            session.flush()
        session.rollback()


def test_heartbeat_rows_and_system_status_distinguish_worker_states(setup, video, worker_id):
    service = monitoring(setup.factory)
    assert service.system_status()["worker"]["state"] in {"OFFLINE", "IDLE"}

    reporter = WorkerHeartbeatReporter(lambda: UnitOfWork(setup.factory), worker_id)
    reporter.beat(WorkerRunState.IDLE, None)
    idle = service.system_status()
    assert idle["worker"]["state"] == "IDLE"
    instance = next(item for item in idle["worker"]["instances"] if item["id"] == worker_id)
    assert instance["alive"] is True and instance["state"] == "IDLE"

    job_id = uuid.UUID(upload(setup, video).json["id"])
    queued = service.system_status()
    assert queued["worker"]["state"] == "QUEUED" and queued["worker"]["queue_depth"] >= 1

    claimed = setup.jobs.claim()
    assert claimed.id == job_id
    reporter.busy(job_id)
    setup.jobs.checkpoint(
        job_id,
        claimed.lease_token,
        20,
        2,
        0,
        0,
        metrics={"source_fps": 20.0, "sampled_fps": 2.0, "detector_ms": 8.0, "tracker_ms": 1.0},
    )
    running = service.system_status()
    assert running["worker"]["state"] == "RUNNING"
    [camera] = [item for item in running["cameras"] if item["id"] == setup.camera["id"]]
    assert camera["worker_state"] == "RUNNING"
    assert camera["metrics"]["processed_fps"] == 2.0
    assert camera["metrics"]["latency_ms"] == 9.0
    assert camera["metrics"]["live"] is True
    assert camera["heartbeat_freshness"]["stale"] is False

    with setup.factory() as session:
        session.execute(
            text(
                "UPDATE worker_heartbeats SET heartbeat_at = now() - interval '10 minutes', "
                "started_at = now() - interval '1 hour' WHERE worker_id = :id"
            ),
            {"id": worker_id},
        )
        session.execute(
            text(
                "UPDATE processing_jobs SET lease_expires_at = now() - interval '1 second' "
                "WHERE id = :id"
            ),
            {"id": job_id},
        )
        session.commit()
    dead = service.system_status()
    assert dead["worker"]["state"] == "ERROR"
    [camera] = [item for item in dead["cameras"] if item["id"] == setup.camera["id"]]
    assert camera["worker_state"] == "ERROR"
    assert camera["last_error"] == "worker_heartbeat_lost"

    with setup.factory() as session:
        session.get(ProcessingJob, job_id).lease_expires_at = datetime.now(UTC) + timedelta(
            minutes=1
        )
        session.commit()
    reporter.beat(WorkerRunState.STOPPED, None)
    stopped = service.system_status()
    assert stopped["worker"]["state"] == "OFFLINE"


def test_prune_keeps_recent_heartbeats(setup, worker_id):
    reporter = WorkerHeartbeatReporter(lambda: UnitOfWork(setup.factory), worker_id)
    reporter.beat(WorkerRunState.IDLE, None)
    other = WorkerHeartbeatReporter(lambda: UnitOfWork(setup.factory), f"{worker_id}-old")
    other.beat(WorkerRunState.STOPPED, None)
    with setup.factory() as session:
        session.execute(
            text(
                "UPDATE worker_heartbeats SET heartbeat_at = now() - interval '8 days', "
                "started_at = now() - interval '9 days' WHERE worker_id = :id"
            ),
            {"id": f"{worker_id}-old"},
        )
        session.commit()

    assert reporter.prune(timedelta(days=7)) == 1
    with setup.factory() as session:
        remaining = set(session.scalars(text("SELECT worker_id FROM worker_heartbeats")))
    assert worker_id in remaining and f"{worker_id}-old" not in remaining
