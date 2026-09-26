from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from person_search.api.errors import ApiError
from person_search.demo import (
    DEMO_ENCODER_SHA256,
    DemoEncoderGateway,
    build_demo_pipeline,
)
from person_search.services.monitoring import (
    HEARTBEAT_STALE_AFTER,
    MonitoringService,
    Outcome,
    WorkerState,
    camera_category,
    camera_metrics,
    connection_state,
    freshness,
    overall,
    run_pipeline_steps,
    worker_alive,
    worker_state,
)
from person_search.services.searches import EncoderUnavailableError
from person_search.storage.postgres.models import CameraStatus, JobStatus, RtspStatus

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)

DEMO_CONFIG = SimpleNamespace(
    detector_name="demo_detector",
    detector_version="1",
    tracker_name="demo_tracker",
    tracker_version="1",
    encoder_name="demo_encoder",
    encoder_version="fake_demo_v1",
    encoder_dimension=256,
    checkpoint_sha256=DEMO_ENCODER_SHA256,
)


def camera(**overrides):
    values = dict(
        status=CameraStatus.ACTIVE,
        ai_enabled=True,
        rtsp_url=None,
        rtsp_credentials=None,
        rtsp_status=RtspStatus.UNKNOWN,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def job(status, **overrides):
    values = dict(status=status, lease_expires_at=None, error_code=None)
    values.update(overrides)
    return SimpleNamespace(**values)


def outcomes(steps):
    return [(step.component, step.outcome) for step in steps]


def test_worker_state_follows_ai_flag_jobs_and_leases() -> None:
    assert worker_state(camera(ai_enabled=False), None, None, NOW)[0] is WorkerState.DISABLED
    assert worker_state(camera(), None, None, NOW)[0] is WorkerState.IDLE
    assert worker_state(camera(), job(JobStatus.PENDING), None, NOW)[0] is WorkerState.QUEUED
    running = job(JobStatus.RUNNING, lease_expires_at=NOW + timedelta(seconds=30))
    assert worker_state(camera(), running, None, NOW)[0] is WorkerState.RUNNING
    stale = job(JobStatus.RUNNING, lease_expires_at=NOW - timedelta(seconds=1))
    assert worker_state(camera(), stale, None, NOW) == (
        WorkerState.ERROR,
        "worker_heartbeat_lost",
    )
    failed = job(JobStatus.FAILED, error_code="detector_failed")
    assert worker_state(camera(), None, failed, NOW) == (WorkerState.ERROR, "detector_failed")
    succeeded = job(JobStatus.SUCCEEDED)
    assert worker_state(camera(), None, succeeded, NOW)[0] is WorkerState.IDLE


def test_camera_category_matches_status_table() -> None:
    assert connection_state(camera()) == "NOT_CONFIGURED"
    online = camera(rtsp_url="rtsp://10.0.0.5/s", rtsp_status=RtspStatus.ONLINE)
    assert camera_category(online, "ONLINE", WorkerState.RUNNING) == "healthy"
    assert camera_category(online, "OFFLINE", WorkerState.IDLE) == "connection_issues"
    assert camera_category(online, "ONLINE", WorkerState.ERROR) == "ai_issues"
    assert camera_category(online, "UNKNOWN", WorkerState.IDLE) == "unknown"
    inactive = camera(status=CameraStatus.INACTIVE)
    assert camera_category(inactive, "NOT_CONFIGURED", WorkerState.DISABLED) == "unknown"
    assert camera_category(camera(), "NOT_CONFIGURED", WorkerState.IDLE) == "healthy"


def test_demo_pipeline_on_upload_camera_succeeds() -> None:
    steps = run_pipeline_steps(camera(), DEMO_CONFIG, lambda *_: "ONLINE", build_demo_pipeline)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.SKIPPED),
        ("DETECTOR", Outcome.SUCCESS),
        ("TRACKER", Outcome.SUCCESS),
        ("IMAGE_ENCODER", Outcome.SUCCESS),
    ]
    assert overall(steps) is Outcome.SUCCESS
    assert "256" in steps[-1].message


def test_pipeline_diagnostic_does_not_fallback_to_demo() -> None:
    steps = run_pipeline_steps(camera(), DEMO_CONFIG, lambda *_: "ONLINE", None)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.SKIPPED),
        ("DETECTOR", Outcome.FAILED),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert "chưa cấu hình pipeline diagnostics" in (steps[1].message or "")


def test_offline_rtsp_fails_and_skips_models() -> None:
    rtsp = camera(rtsp_url="rtsp://10.0.0.5/s")
    steps = run_pipeline_steps(rtsp, DEMO_CONFIG, lambda *_: "OFFLINE", build_demo_pipeline)

    assert outcomes(steps)[0] == ("FRAME_SOURCE", Outcome.FAILED)
    assert {step.outcome for step in steps[1:]} == {Outcome.SKIPPED}
    assert overall(steps) is Outcome.FAILED


def test_forbidden_rtsp_host_is_reported_not_raised() -> None:
    def probe(*_):
        raise ApiError(422, "rtsp_host_forbidden", "Host bị chặn.")

    steps = run_pipeline_steps(
        camera(rtsp_url="rtsp://127.0.0.1/s"), DEMO_CONFIG, probe, build_demo_pipeline
    )

    assert steps[0].outcome is Outcome.FAILED and steps[0].message == "Host bị chặn."


def test_unsupported_config_and_ai_disabled_fail() -> None:
    other = SimpleNamespace(**{**vars(DEMO_CONFIG), "detector_name": "yolov8m"})
    steps = run_pipeline_steps(camera(), other, lambda *_: "ONLINE", build_demo_pipeline)
    assert outcomes(steps)[1] == ("DETECTOR", Outcome.FAILED)

    disabled = run_pipeline_steps(
        camera(ai_enabled=False), DEMO_CONFIG, lambda *_: "ONLINE", build_demo_pipeline
    )
    assert disabled[0].outcome is Outcome.FAILED
    assert overall(disabled) is Outcome.FAILED


def test_empty_detection_is_inconclusive() -> None:
    class NoPeople:
        def detect(self, frame):
            return []

    def factory(config):
        pipeline = build_demo_pipeline(config)
        pipeline.detector = NoPeople()
        return pipeline

    steps = run_pipeline_steps(camera(), DEMO_CONFIG, lambda *_: "ONLINE", factory)

    assert outcomes(steps)[1] == ("DETECTOR", Outcome.INCONCLUSIVE)
    assert overall(steps) is Outcome.INCONCLUSIVE


class FakeSearch:
    def __init__(self, gateway=None, config=DEMO_CONFIG):
        self._gateway = gateway or DemoEncoderGateway()
        self._config = config

    def active_config(self):
        if self._config is None:
            raise EncoderUnavailableError("none")
        return self._config

    def gateway(self, version):
        return self._gateway


class FakeHealth:
    def __init__(self, **states):
        self.states = states

    def check(self):
        return SimpleNamespace(
            components={name: {"status": state} for name, state in self.states.items()}
        )


def service(search, health):
    return MonitoringService(
        lambda: None, health=health, search=search, runtime=None, clock=lambda: NOW
    )


def test_search_components_with_demo_encoder() -> None:
    report = service(
        FakeSearch(), FakeHealth(postgres="ok", milvus="ok", minio="error")
    ).search_components()

    components = {step["component"]: step["outcome"] for step in report["steps"]}
    assert components["TEXT_ENCODER"] == "SUCCESS"
    assert components["IMAGE_ENCODER"] == "SUCCESS"
    assert components["STORAGE_MINIO"] == "FAILED"
    assert report["overall"] == "FAILED"
    assert report["ran_at"] == "2026-09-25T08:00:00Z"


def test_search_components_reports_broken_encoder() -> None:
    class Broken:
        def text(self, *args, **kwargs):
            raise EncoderUnavailableError("down")

        def image(self, *args, **kwargs):
            return [1.0, 0.0]

    report = service(FakeSearch(Broken()), FakeHealth(postgres="ok")).search_components()
    components = {step["component"]: step for step in report["steps"]}
    assert components["TEXT_ENCODER"]["outcome"] == "FAILED"
    assert "chiều" in components["IMAGE_ENCODER"]["message"]

    missing = service(FakeSearch(config=None), FakeHealth()).search_components()
    assert [step["outcome"] for step in missing["steps"]] == ["FAILED", "SKIPPED", "SKIPPED"]


def test_encoder_status_uses_gateway() -> None:
    assert service(FakeSearch(), FakeHealth())._encoder_status() == "UP"
    assert service(FakeSearch(config=None), FakeHealth())._encoder_status() == "DOWN"


def test_camera_pipeline_unknown_camera_is_404() -> None:
    work = SimpleNamespace(
        repositories=SimpleNamespace(
            cameras=SimpleNamespace(get=lambda _: None),
            ai_configs=SimpleNamespace(active=lambda: DEMO_CONFIG),
        )
    )

    class Work:
        def __enter__(self):
            return work

        def __exit__(self, *args):
            return None

    monitoring = MonitoringService(
        Work, health=FakeHealth(), search=FakeSearch(), runtime=None, clock=lambda: NOW
    )
    with pytest.raises(ApiError) as caught:
        monitoring.camera_pipeline(uuid.uuid4())
    assert caught.value.status == 404


def heartbeat(age_seconds, state="IDLE", **overrides):
    values = dict(
        worker_id="host:1",
        state=state,
        current_job_id=None,
        started_at=NOW - timedelta(hours=1),
        heartbeat_at=NOW - timedelta(seconds=age_seconds),
        state_changed_at=NOW - timedelta(hours=1),
        rss_bytes=1024,
        cpu_percent=12.5,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def full_job(status, **overrides):
    values = dict(
        id=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        status=status,
        lease_expires_at=NOW + timedelta(seconds=30),
        heartbeat_at=NOW - timedelta(seconds=2),
        error_code=None,
        created_at=NOW - timedelta(minutes=5),
        ended_at=None,
        metrics={},
        metrics_updated_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def status_camera(**overrides):
    values = dict(
        id=uuid.uuid4(),
        code="CAM-01",
        name="Camera 1",
        status=CameraStatus.ACTIVE,
        ai_enabled=True,
        rtsp_url=None,
        rtsp_credentials=None,
        rtsp_status=RtspStatus.UNKNOWN,
        last_checked_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


AREA = SimpleNamespace(name="Area A")


def test_freshness_marks_missing_and_old_observations_stale():
    assert freshness(None, NOW, timedelta(seconds=45)) == {
        "observed_at": None,
        "age_seconds": None,
        "stale": True,
    }
    fresh = freshness(NOW - timedelta(seconds=10), NOW, timedelta(seconds=45))
    assert fresh == {"observed_at": "2026-09-25T07:59:50Z", "age_seconds": 10.0, "stale": False}
    naive = datetime(2026, 9, 25, 7, 59)
    assert freshness(naive, NOW, timedelta(seconds=45))["stale"] is True
    assert freshness(NOW + timedelta(seconds=5), NOW, timedelta(seconds=1))["age_seconds"] == 0


def test_worker_alive_requires_fresh_non_stopped_heartbeat():
    assert worker_alive(None, NOW) is False
    assert worker_alive(heartbeat(5), NOW) is True
    assert worker_alive(heartbeat(5, state="STOPPED"), NOW) is False
    assert worker_alive(heartbeat(HEARTBEAT_STALE_AFTER.total_seconds() + 1), NOW) is False


def test_worker_state_distinguishes_offline_queue_and_retry_wait():
    pending = job(JobStatus.PENDING)
    assert worker_state(camera(), pending, None, NOW, alive=False) == (
        WorkerState.QUEUED,
        "worker_offline",
    )
    assert worker_state(camera(), pending, None, NOW, alive=True) == (WorkerState.QUEUED, None)
    retry = job(
        JobStatus.RUNNING,
        lease_expires_at=NOW - timedelta(seconds=1),
        error_code="storage_unavailable",
    )
    assert worker_state(camera(), retry, None, NOW) == (
        WorkerState.QUEUED,
        "storage_unavailable",
    )
    assert worker_state(camera(ai_enabled=False), pending, None, NOW, alive=False) == (
        WorkerState.DISABLED,
        None,
    )


def test_offline_queue_is_an_ai_issue():
    assert camera_category(camera(), "NOT_CONFIGURED", WorkerState.QUEUED, "worker_offline") == (
        "ai_issues"
    )
    assert camera_category(camera(), "NOT_CONFIGURED", WorkerState.QUEUED) == "healthy"


def test_camera_metrics_expose_bounded_live_values_and_failures():
    running = full_job(
        JobStatus.RUNNING,
        metrics={
            "source_fps": 25.0,
            "sampled_fps": 2.5,
            "detector_ms": 40.0,
            "tracker_ms": 2.0,
            "encoder_ms": 300.0,
            "queue_ms": 1500.0,
            "track_count": 3.0,
            "error_count": 1.0,
            "rss_bytes": 2048.0,
            "cpu_percent": 90.0,
            "unexpected": "rtsp://admin:secret@host",
        },
        metrics_updated_at=NOW - timedelta(seconds=3),
    )

    metrics = camera_metrics(running, 2, NOW, live=True)

    assert metrics["source_fps"] == 25.0
    assert metrics["processed_fps"] == 2.5
    assert metrics["latency_ms"] == 42.0
    assert metrics["encoder_ms"] == 300.0
    assert metrics["retries"] == 1.0
    assert metrics["error_count"] == 2
    assert metrics["live"] is True
    assert metrics["freshness"]["stale"] is False
    assert "unexpected" not in metrics and "secret" not in str(metrics)


def test_camera_metrics_without_job_are_empty_and_not_live():
    metrics = camera_metrics(None, 0, NOW, live=False)
    assert metrics["source_fps"] is None and metrics["processed_fps"] is None
    assert metrics["latency_ms"] is None and metrics["live"] is False
    assert metrics["freshness"]["stale"] is True


def test_worker_summary_states():
    subject = service(FakeSearch(), FakeHealth())
    alive = [heartbeat(3)]
    running = full_job(JobStatus.RUNNING)
    pending = full_job(JobStatus.PENDING, created_at=NOW - timedelta(minutes=7))

    idle = subject._worker([], alive, None, NOW, True)
    assert idle["state"] == "IDLE" and idle["queue_depth"] == 0
    assert idle["freshness"]["stale"] is False
    assert idle["instances"][0]["alive"] is True
    assert idle["instances"][0]["rss_bytes"] == 1024

    busy = subject._worker([running, pending], alive, None, NOW, True)
    assert busy["state"] == "RUNNING" and busy["queue_depth"] == 1
    assert busy["oldest_queued_at"] == "2026-09-25T07:53:00Z"

    queued = subject._worker([pending], alive, None, NOW, True)
    assert queued["state"] == "QUEUED"

    waiting = full_job(JobStatus.RUNNING, error_code="storage_unavailable")
    retry = subject._worker([waiting], alive, None, NOW, True)
    assert retry["state"] == "QUEUED" and retry["retry_waiting"] == 1

    dead = subject._worker([pending], [heartbeat(600)], None, NOW, False)
    assert dead["state"] == "OFFLINE"
    assert dead["freshness"]["stale"] is True
    assert dead["instances"][0]["alive"] is False

    never = subject._worker([], [], None, NOW, False)
    assert never["state"] == "OFFLINE" and never["instances"] == []
    assert never["last_heartbeat_at"] is None

    lost = full_job(JobStatus.RUNNING, lease_expires_at=NOW - timedelta(seconds=1))
    assert subject._worker([lost], alive, None, NOW, True)["state"] == "ERROR"


def test_camera_rows_report_freshness_metrics_and_rtsp_state():
    subject = service(FakeSearch(), FakeHealth())
    running_camera = status_camera(
        rtsp_url="rtsp://10.0.0.5/s",
        rtsp_credentials="admin:secret",
        rtsp_status=RtspStatus.OFFLINE,
        last_checked_at=NOW - timedelta(minutes=10),
    )
    idle_camera = status_camera(code="CAM-02")
    disabled_camera = status_camera(code="CAM-03", ai_enabled=False)
    running = full_job(
        JobStatus.RUNNING,
        camera_id=running_camera.id,
        metrics={"sampled_fps": 2.0, "detector_ms": 10.0, "tracker_ms": 1.0},
        metrics_updated_at=NOW - timedelta(seconds=1),
    )
    failed = full_job(
        JobStatus.FAILED,
        camera_id=idle_camera.id,
        error_code="detector_inference_failed",
        ended_at=NOW - timedelta(minutes=1),
        metrics={"sampled_fps": 1.0},
        metrics_updated_at=NOW - timedelta(minutes=1),
    )

    rows = subject._camera_rows(
        [(running_camera, AREA), (idle_camera, AREA), (disabled_camera, AREA)],
        [running],
        {idle_camera.id: failed},
        {idle_camera.id: 3},
        NOW,
        alive=True,
    )
    first, second, third = rows

    assert first["worker_state"] == "RUNNING"
    assert first["connection"] == "OFFLINE"
    assert first["connection_freshness"]["stale"] is True
    assert first["category"] == "connection_issues"
    assert first["heartbeat_freshness"]["stale"] is False
    assert first["metrics"]["processed_fps"] == 2.0 and first["metrics"]["latency_ms"] == 11.0
    assert first["metrics"]["live"] is True
    assert "secret" not in str(first) and "rtsp://" not in str(first)

    assert second["worker_state"] == "ERROR"
    assert second["last_error"] == "detector_inference_failed"
    assert second["connection"] == "NOT_CONFIGURED"
    assert second["connection_freshness"] is None
    assert second["heartbeat_freshness"] is None
    assert second["last_job_status"] == "FAILED"
    assert second["metrics"]["live"] is False
    assert second["metrics"]["processed_fps"] == 1.0
    assert second["metrics"]["error_count"] == 3

    assert third["worker_state"] == "DISABLED"
    assert third["metrics"]["error_count"] == 0


def test_camera_rows_flag_pending_work_when_worker_is_dead():
    subject = service(FakeSearch(), FakeHealth())
    queued_camera = status_camera()
    pending = full_job(JobStatus.PENDING, camera_id=queued_camera.id)

    [row] = subject._camera_rows([(queued_camera, AREA)], [pending], {}, {}, NOW, alive=False)

    assert (row["worker_state"], row["last_error"], row["category"]) == (
        "QUEUED",
        "worker_offline",
        "ai_issues",
    )


def test_encoder_status_reads_configuration_without_running_inference():
    class Tracking:
        def text(self, *args, **kwargs):
            raise AssertionError("status must not run text inference")

        def image(self, *args, **kwargs):
            raise AssertionError("status must not run image inference")

    assert service(FakeSearch(Tracking()), FakeHealth())._encoder_status() == "UP"

    class Unconfigured(FakeSearch):
        def gateway(self, version):
            raise EncoderUnavailableError("missing")

    assert service(Unconfigured(), FakeHealth())._encoder_status() == "DOWN"


class StatusSession:
    def __init__(self, results):
        self.results = list(results)

    def execute(self, statement):
        return SimpleNamespace(all=lambda: self.results.pop(0))

    def scalars(self, statement):
        return iter(self.results.pop(0))

    def scalar(self, statement):
        return self.results.pop(0)


def status_service(results, search=None, health=None):
    class Work:
        def __init__(self):
            self.session = StatusSession(results)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    return MonitoringService(
        Work,
        health=health or FakeHealth(postgres="ok", milvus="ok", minio="ok"),
        search=search or FakeSearch(),
        runtime=None,
        clock=lambda: NOW,
    )


def test_system_status_snapshot_combines_cameras_worker_and_components():
    running_camera = status_camera()
    running = full_job(
        JobStatus.RUNNING,
        camera_id=running_camera.id,
        metrics={"source_fps": 20.0},
        metrics_updated_at=NOW - timedelta(seconds=1),
    )
    beat = heartbeat(4, state="BUSY", current_job_id=running.id)
    subject = status_service(
        [
            [(running_camera, AREA)],
            [running],
            [],
            [],
            [beat],
            NOW - timedelta(seconds=2),
        ]
    )

    status = subject.system_status()

    assert status["generated_at"] == "2026-09-25T08:00:00Z"
    assert status["worker"]["state"] == "RUNNING"
    assert status["worker"]["instances"][0]["current_job_id"] == str(running.id)
    assert status["cameras"][0]["worker_state"] == "RUNNING"
    assert status["cameras"][0]["metrics"]["source_fps"] == 20.0
    assert status["summary"]["healthy"] == 1
    components = {item["component"]: item for item in status["components"]}
    assert components["AI_WORKER"]["state"] == "RUNNING"
    assert components["AI_WORKER"]["checked_at"] == "2026-09-25T07:59:56Z"
    assert components["SEARCH_ENCODER"]["state"] == "UP"
    assert components["STORAGE_POSTGRES"]["state"] == "UP"
    assert status["encoder"] == "UP" and status["storage"]["minio"] == "UP"


def test_system_status_reports_dead_worker_without_heartbeat_rows():
    queued_camera = status_camera()
    pending = full_job(JobStatus.PENDING, camera_id=queued_camera.id)
    subject = status_service([[(queued_camera, AREA)], [pending], [], [], [], None])

    status = subject.system_status()

    assert status["worker"]["state"] == "OFFLINE"
    assert status["worker"]["queue_depth"] == 1
    assert status["cameras"][0]["last_error"] == "worker_offline"
    assert status["summary"]["ai_issues"] == 1
