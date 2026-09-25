from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from person_search.api.errors import ApiError
from person_search.services.monitoring import (
    MonitoringService,
    Outcome,
    WorkerState,
    camera_category,
    connection_state,
    overall,
    run_pipeline_steps,
    worker_state,
)
from person_search.services.searches import DemoEncoderGateway, EncoderUnavailableError
from person_search.storage.postgres.models import CameraStatus, JobStatus, RtspStatus
from person_search.workers.pipeline import Pipeline

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
    checkpoint_sha256="0" * 64,
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
    steps = run_pipeline_steps(camera(), DEMO_CONFIG, lambda *_: "ONLINE", Pipeline.demo)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.SKIPPED),
        ("DETECTOR", Outcome.SUCCESS),
        ("TRACKER", Outcome.SUCCESS),
        ("IMAGE_ENCODER", Outcome.SUCCESS),
    ]
    assert overall(steps) is Outcome.SUCCESS
    assert "256" in steps[-1].message


def test_offline_rtsp_fails_and_skips_models() -> None:
    rtsp = camera(rtsp_url="rtsp://10.0.0.5/s")
    steps = run_pipeline_steps(rtsp, DEMO_CONFIG, lambda *_: "OFFLINE", Pipeline.demo)

    assert outcomes(steps)[0] == ("FRAME_SOURCE", Outcome.FAILED)
    assert {step.outcome for step in steps[1:]} == {Outcome.SKIPPED}
    assert overall(steps) is Outcome.FAILED


def test_forbidden_rtsp_host_is_reported_not_raised() -> None:
    def probe(*_):
        raise ApiError(422, "rtsp_host_forbidden", "Host bị chặn.")

    steps = run_pipeline_steps(
        camera(rtsp_url="rtsp://127.0.0.1/s"), DEMO_CONFIG, probe, Pipeline.demo
    )

    assert steps[0].outcome is Outcome.FAILED and steps[0].message == "Host bị chặn."


def test_unsupported_config_and_ai_disabled_fail() -> None:
    other = SimpleNamespace(**{**vars(DEMO_CONFIG), "detector_name": "yolov8m"})
    steps = run_pipeline_steps(camera(), other, lambda *_: "ONLINE", Pipeline.demo)
    assert outcomes(steps)[1] == ("DETECTOR", Outcome.FAILED)

    disabled = run_pipeline_steps(
        camera(ai_enabled=False), DEMO_CONFIG, lambda *_: "ONLINE", Pipeline.demo
    )
    assert disabled[0].outcome is Outcome.FAILED
    assert overall(disabled) is Outcome.FAILED


def test_empty_detection_is_inconclusive() -> None:
    class NoPeople:
        def detect(self, frame):
            return []

    def factory(config):
        pipeline = Pipeline.demo(config)
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
