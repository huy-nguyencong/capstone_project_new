from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from person_search.storage.postgres.models import WorkerHeartbeat
from person_search.workers.production import StageTiming
from person_search.workers.telemetry import (
    JOB_METRIC_KEYS,
    JobMetricsCollector,
    ResourceSampler,
    WorkerHeartbeatReporter,
    WorkerRunState,
    default_worker_id,
    sanitize_metrics,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


class Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class FixedResources:
    def __init__(self, values=None) -> None:
        self.values = values if values is not None else {"rss_bytes": 1024.0, "cpu_percent": 50.0}
        self.calls = 0

    def sample(self):
        self.calls += 1
        return dict(self.values)


def test_sanitize_metrics_keeps_only_bounded_numeric_allowlist():
    clean = sanitize_metrics(
        {
            "source_fps": 25,
            "sampled_fps": 2.5,
            "detector_ms": float("nan"),
            "tracker_ms": float("inf"),
            "encoder_ms": -1,
            "track_count": True,
            "queue_ms": "12",
            "rss_bytes": 1e30,
            "rtsp_url": "rtsp://admin:secret@10.0.0.5/stream",
            "query": "a person in a red coat",
            "camera_id": str(uuid.uuid4()),
            7: 1,
        }
    )

    assert clean == {"rss_bytes": 1e15, "sampled_fps": 2.5, "source_fps": 25.0}
    assert set(clean) <= JOB_METRIC_KEYS
    assert "secret" not in str(clean)


def test_sanitize_metrics_rounds_values():
    assert sanitize_metrics({"detector_ms": 12.34567}) == {"detector_ms": 12.346}


def test_resource_sampler_reports_cpu_percent_between_samples():
    wall = Clock(10.0)
    cpu = Clock(1.0)
    sampler = ResourceSampler(clock=wall, cpu_time=cpu, rss=lambda: 4096)
    wall.value, cpu.value = 12.0, 2.0

    sample = sampler.sample()

    assert sample == {"cpu_percent": 50.0, "rss_bytes": 4096.0}
    assert "cpu_percent" not in ResourceSampler(clock=Clock(), rss=lambda: None).sample()


def test_resource_sampler_omits_unknown_rss():
    wall = Clock(0.0)
    sampler = ResourceSampler(clock=wall, cpu_time=Clock(0.0), rss=lambda: None)
    wall.value = 1.0
    assert sampler.sample() == {"cpu_percent": 0.0}


def test_job_metrics_collector_computes_rates_latencies_queue_and_errors():
    clock = Clock(100.0)
    claimed = SimpleNamespace(
        created_at=NOW,
        started_at=NOW + timedelta(seconds=3),
        attempts=3,
    )
    collector = JobMetricsCollector.for_claimed(
        claimed, clock=clock, resources=FixedResources(), interval_seconds=2
    )
    collector.attach(
        lambda: (
            StageTiming("load", 1, 900.0),
            StageTiming("detector", 4, 400.0),
            StageTiming("tracker", 4, 40.0),
            StageTiming("image_encoder", 2, 1000.0),
        )
    )
    clock.value = 104.0

    metrics = collector.snapshot(100, 10, 2)

    assert metrics == {
        "cpu_percent": 50.0,
        "detector_ms": 100.0,
        "elapsed_ms": 4000.0,
        "encoder_ms": 500.0,
        "error_count": 2.0,
        "queue_ms": 3000.0,
        "rss_bytes": 1024.0,
        "sampled_fps": 2.5,
        "source_fps": 25.0,
        "track_count": 2.0,
        "tracker_ms": 10.0,
    }


def test_job_metrics_collector_throttles_until_interval_elapses():
    clock = Clock(0.0)
    collector = JobMetricsCollector(clock=clock, resources=FixedResources(), interval_seconds=2)

    assert collector.due() is True
    collector.snapshot(0, 0, 0)
    clock.value = 1.5
    assert collector.due() is False
    clock.value = 2.0
    assert collector.due() is True


def test_job_metrics_collector_tolerates_missing_or_broken_timings():
    clock = Clock(0.0)
    collector = JobMetricsCollector(clock=clock, resources=FixedResources({}))

    def broken():
        raise RuntimeError("model path /secret/weights.pt")

    collector.attach(broken)
    metrics = collector.snapshot(0, 0, 0)

    assert metrics == {"elapsed_ms": 0.0, "error_count": 0.0, "track_count": 0.0}
    assert "queue_ms" not in metrics


def test_job_metrics_collector_rejects_negative_interval():
    with pytest.raises(ValueError):
        JobMetricsCollector(interval_seconds=-1)


def test_new_attempt_collector_resets_elapsed_and_rates():
    clock = Clock(0.0)
    first = JobMetricsCollector(clock=clock, resources=FixedResources({}))
    clock.value = 100.0
    assert first.snapshot(1000, 100, 5)["elapsed_ms"] == 100000.0

    second = JobMetricsCollector.for_claimed(
        SimpleNamespace(attempts=2), clock=clock, resources=FixedResources({})
    )
    clock.value = 101.0
    metrics = second.snapshot(10, 1, 0)
    assert metrics["elapsed_ms"] == 1000.0
    assert metrics["source_fps"] == 10.0
    assert metrics["error_count"] == 1.0


def test_default_worker_id_is_sanitized_and_bounded(monkeypatch):
    monkeypatch.setenv("PERSON_SEARCH_WORKER_ID", "host a/b?password=x" + "z" * 200)
    worker_id = default_worker_id()
    assert "/" not in worker_id and "?" not in worker_id and "=" not in worker_id
    assert len(worker_id) == 128

    monkeypatch.delenv("PERSON_SEARCH_WORKER_ID")
    assert default_worker_id()


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.locked = []
        self.deleted = 0

    def get(self, model, key, with_for_update=False):
        assert model is WorkerHeartbeat
        self.locked.append(with_for_update)
        return self.rows.get(key)

    def add(self, row):
        self.rows[row.worker_id] = row

    def execute(self, statement):
        cutoff = statement.whereclause.clauses[0].right.value
        keep = statement.whereclause.clauses[1].right.value
        stale = [
            key
            for key, row in self.rows.items()
            if row.heartbeat_at < cutoff and key != keep
        ]
        for key in stale:
            del self.rows[key]
        return SimpleNamespace(rowcount=len(stale))


class FakeWork:
    def __init__(self, session) -> None:
        self.session = session
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def commit(self):
        self.commits += 1


def reporter(rows, clock, **kwargs):
    session = FakeSession(rows)
    work = FakeWork(session)
    subject = WorkerHeartbeatReporter(
        lambda: work,
        "host:1",
        clock=clock,
        resources=FixedResources(),
        pid=lambda: 4321,
        **kwargs,
    )
    return subject, session, work


def test_heartbeat_reporter_creates_row_and_tracks_state_changes():
    rows = {}
    now = {"value": NOW}
    subject, session, work = reporter(rows, lambda: now["value"])

    subject.beat(WorkerRunState.IDLE, None)
    row = rows["host:1"]
    assert (row.state, row.pid, row.rss_bytes, row.cpu_percent) == ("IDLE", 4321, 1024, 50.0)
    assert row.started_at == row.heartbeat_at == row.state_changed_at == NOW
    assert session.locked == [True]

    job_id = uuid.uuid4()
    now["value"] = NOW + timedelta(seconds=10)
    subject.busy(job_id)
    assert (row.state, row.current_job_id) == ("BUSY", job_id)
    assert row.state_changed_at == NOW + timedelta(seconds=10)

    now["value"] = NOW + timedelta(seconds=20)
    subject.beat()
    assert row.state == "BUSY" and row.current_job_id == job_id
    assert row.state_changed_at == NOW + timedelta(seconds=10)
    assert row.heartbeat_at == NOW + timedelta(seconds=20)

    subject.idle()
    assert (row.state, row.current_job_id) == ("IDLE", None)
    assert work.commits == 4


def test_child_reporter_does_not_overwrite_process_resources():
    rows = {
        "host:1": WorkerHeartbeat(
            worker_id="host:1",
            state="IDLE",
            pid=11,
            rss_bytes=5,
            cpu_percent=1.0,
            started_at=NOW,
            heartbeat_at=NOW,
            state_changed_at=NOW,
        )
    }
    subject, _, _ = reporter(
        rows, lambda: NOW + timedelta(seconds=5), report_process=False
    )

    subject.busy(uuid.uuid4())

    row = rows["host:1"]
    assert (row.pid, row.rss_bytes, row.cpu_percent) == (11, 5, 1.0)
    assert row.state == "BUSY"


def test_safe_beat_swallows_storage_failure_without_leaking_detail(caplog):
    class Broken:
        def __enter__(self):
            raise ConnectionError("postgresql://user:secret@db/app")

        def __exit__(self, *args):
            return None

    subject = WorkerHeartbeatReporter(Broken, "host:1", resources=FixedResources())

    assert subject.safe_beat(WorkerRunState.IDLE) is False
    assert subject.busy(uuid.uuid4()) is False
    assert "secret" not in caplog.text
    assert "ConnectionError" in caplog.text


def test_prune_removes_only_old_foreign_heartbeats():
    old = NOW - timedelta(days=8)
    rows = {
        name: WorkerHeartbeat(
            worker_id=name,
            state="STOPPED",
            started_at=old,
            heartbeat_at=at,
            state_changed_at=old,
        )
        for name, at in (("host:1", old), ("host:2", old), ("host:3", NOW))
    }
    subject, _, _ = reporter(rows, lambda: NOW)

    assert subject.prune(timedelta(days=7)) == 1
    assert set(rows) == {"host:1", "host:3"}
    with pytest.raises(ValueError):
        subject.prune(timedelta(0))


def test_reporter_rejects_invalid_worker_id():
    for value in ("", "x" * 129):
        with pytest.raises(ValueError):
            WorkerHeartbeatReporter(lambda: None, value, resources=FixedResources())


def test_heartbeat_model_has_no_sensitive_columns():
    columns = set(WorkerHeartbeat.__table__.columns.keys())
    assert columns == {
        "worker_id",
        "state",
        "current_job_id",
        "pid",
        "started_at",
        "heartbeat_at",
        "state_changed_at",
        "rss_bytes",
        "cpu_percent",
    }
    assert not any(
        word in name for name in columns for word in ("url", "credential", "query", "frame")
    )
