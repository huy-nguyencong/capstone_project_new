from __future__ import annotations

import io
import json
import logging
import re
import threading
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from person_search import create_app
from person_search.observability import (
    REDACTED,
    ContextFilter,
    JsonFormatter,
    RedactionFilter,
    bind_context,
    configure_logging,
    current_context,
    install_filters,
    log_context,
    redact_text,
    redact_value,
    reset_context,
)
from person_search.services.audit import AuditEvent
from person_search.services.diagnostics import Outcome, Step
from person_search.services.jobs import failure_stage
from person_search.services.monitoring import MonitoringService
from person_search.storage.postgres.models import AuditResult, CameraStatus, JobSourceType
from person_search.workers.durable import SequentialProductionWorker
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

SECRET_PATTERNS = (
    re.compile(r"rtsp://[^\s\[]*:[^\s\[]*@"),
    re.compile(r"X-Amz-Signature=[0-9a-f]"),
    re.compile(r"hunter2"),
    re.compile(r"red coat"),
    re.compile(r"0\.123456"),
    re.compile(r"postgresql://[^\s\[]+@"),
)


def assert_no_secrets(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def capture(name: str = "person_search.test_observability"):
    stream = io.StringIO()
    handler = install_filters(logging.StreamHandler(stream))
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, handler, stream


def records(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


@pytest.fixture
def captured():
    logger, handler, stream = capture()
    yield logger, stream
    logger.removeHandler(handler)


def test_redact_text_covers_credentials_signed_urls_vectors_and_blobs():
    vector = "[" + ", ".join(f"0.{index:06d}" for index in range(20)) + "]"
    text = redact_text(
        "open rtsp://admin:hunter2@10.0.0.5/live "
        "url=http://minio:9000/frames/a.jpg?X-Amz-Algorithm=AWS4&X-Amz-Signature=deadbeef&x=1 "
        f"vector={vector} blob={'QUJD' * 60} raw=b'" + "\\x00" * 40 + "'\nFAKE ENTRY"
    )

    assert "hunter2" not in text and "rtsp://[REDACTED]@10.0.0.5/live" in text
    assert "deadbeef" not in text and "X-Amz-Signature=[REDACTED]" in text
    assert "&x=1" in text
    assert "0.000001" not in text
    assert "QUJDQUJD" not in text
    assert "\\x00" not in text
    assert "\n" not in text


def test_redact_text_keeps_short_numbers_and_hashes():
    digest = "a" * 64
    text = redact_text(f"frames=[1, 2, 3] sha={digest}")
    assert text == f"frames=[1, 2, 3] sha={digest}"


def test_redact_value_by_key_and_shape():
    value = redact_value(
        {
            "query": "a person in a red coat",
            "prompt": "red coat",
            "embedding": [0.1] * 4,
            "rtsp_credentials": "gAAAAA",
            "signed_url": "http://x/y?X-Amz-Signature=1",
            "scores": [0.5] * 32,
            "image_bytes": b"\x89PNG",
            "note": "rtsp://u:hunter2@h/s",
            "track_id": uuid.UUID(int=1),
            "at": datetime(2026, 9, 26, tzinfo=UTC),
            "nested": {"level": {"deeper": {"deepest": {"bottom": {"x": 1}}}}},
        }
    )

    for key in ("query", "prompt", "embedding", "rtsp_credentials", "signed_url", "image_bytes"):
        assert value[key] == REDACTED
    assert value["scores"] == REDACTED
    assert "hunter2" not in value["note"]
    assert value["track_id"] == str(uuid.UUID(int=1))
    assert value["at"].startswith("2026-09-26")
    assert REDACTED in json.dumps(value["nested"])


def test_log_context_nests_resets_and_sanitizes_identifiers():
    job_id = uuid.uuid4()
    with log_context(job_id=job_id, camera_id="cam\nFAKE=1"):
        assert current_context()["job_id"] == str(job_id)
        assert current_context()["camera_id"] == "camFAKE1"
        with log_context(track_id="t-1", camera_id=None):
            assert current_context() == {"job_id": str(job_id), "track_id": "t-1"}
        assert "track_id" not in current_context()
    assert current_context() == {}
    with pytest.raises(ValueError):
        with log_context(query="secret"):
            pass

    token = bind_context(request_id="req-12345678")
    assert current_context()["request_id"] == "req-12345678"
    reset_context(token)
    assert current_context() == {}


def test_structured_log_carries_correlation_and_redacts_message_args_and_extra(captured):
    logger, stream = captured
    job_id, camera_id = uuid.uuid4(), uuid.uuid4()

    with log_context(job_id=job_id, camera_id=camera_id, ai_config_version_id="cfg-1"):
        logger.warning(
            "connect %s failed\nINFO forged line",
            "rtsp://admin:hunter2@10.0.0.5/s",
            extra={"query": "red coat", "error_type": "TimeoutError", "values": [0.123456] * 3},
        )

    [entry] = records(stream)
    assert entry["job_id"] == str(job_id) and entry["camera_id"] == str(camera_id)
    assert entry["ai_config_version_id"] == "cfg-1"
    assert entry["level"] == "WARNING"
    assert "forged line" in entry["message"] and "\n" not in entry["message"]
    assert entry["extra"]["query"] == REDACTED
    assert entry["extra"]["values"] == REDACTED
    assert entry["extra"]["error_type"] == "TimeoutError"
    assert len(stream.getvalue().splitlines()) == 1
    assert_no_secrets(stream.getvalue())


def test_exception_stack_is_kept_internally_but_redacted(captured):
    logger, stream = captured
    try:
        raise ConnectionError("postgresql://user:hunter2@db:5432/app refused")
    except ConnectionError:
        logger.exception("storage exception")

    [entry] = records(stream)
    assert "Traceback" in entry["exception"]
    assert "ConnectionError" in entry["exception"]
    assert_no_secrets(stream.getvalue())


def test_explicit_extra_correlation_overrides_context(captured):
    logger, stream = captured
    with log_context(job_id="job-a"):
        logger.info("override", extra={"job_id": "job-b"})
    assert records(stream)[0]["job_id"] == "job-b"


def test_concurrent_jobs_keep_isolated_correlation(captured):
    logger, stream = captured
    barrier = threading.Barrier(4)

    def work(name: str) -> None:
        with log_context(job_id=name, camera_id=f"cam-{name}"):
            barrier.wait()
            for index in range(20):
                logger.info("progress %d", index)

    threads = [threading.Thread(target=work, args=(f"job-{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    entries = records(stream)
    assert len(entries) == 80
    assert all(entry["camera_id"] == f"cam-{entry['job_id']}" for entry in entries)
    assert {entry["job_id"] for entry in entries} == {f"job-{i}" for i in range(4)}


def test_filters_are_idempotent_and_configure_logging_installs_once():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "rtsp://a:hunter2@h", (), None)
    redaction = RedactionFilter()
    assert redaction.filter(record) and redaction.filter(record)
    assert ContextFilter().filter(record)
    assert "hunter2" not in record.getMessage()

    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    try:
        first = configure_logging("DEBUG", stream=io.StringIO(), json_format=True)
        second = configure_logging("DEBUG", stream=io.StringIO(), json_format=True)
        assert first is second
        assert sum(1 for handler in root.handlers if handler is first) == 1
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
        root.setLevel(level)


class Lock:
    def __enter__(self):
        return True

    def __exit__(self, *args):
        return None


class Jobs:
    def __init__(self, job):
        self.queue = [job]
        self.finished = []

    def cleanup(self):
        return None

    def claim(self):
        return self.queue.pop(0) if self.queue else None

    def checkpoint(self, *args, **kwargs):
        return True

    def finish(self, job_id, token, status, error_code=None):
        self.finished.append((status, error_code))

    def defer_retry(self, *args):
        return True


class Source:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def claimed_job():
    return SimpleNamespace(
        id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        source_type=JobSourceType.FILE,
        source_ref="clip.mp4",
        sampling_interval=10,
        timeline_origin_utc=datetime(2026, 9, 26, tzinfo=UTC),
        attempts=1,
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            AIWorkerError(
                AIErrorCode.DETECTOR_OUTPUT_INVALID,
                internal_detail="rtsp://admin:hunter2@10.0.0.5/s",
            ),
            "detector_output_invalid",
        ),
        (
            RuntimeError("model /models/yolo.pt at postgresql://u:hunter2@db/app"),
            "worker_execution_failed",
        ),
    ],
)
def test_worker_failure_logs_are_correlated_redacted_and_public_code_is_stable(error, expected):
    logger, handler, stream = capture("person_search.workers.durable")
    job = claimed_job()

    class Pipeline:
        def run(self, source):
            raise error

    jobs = Jobs(job)
    worker = SequentialProductionWorker(
        jobs,
        lock_factory=Lock,
        source_factory=lambda snapshot: Source(),
        pipeline_factory=lambda snapshot, cancelled, progress: Pipeline(),
        result_consumer=lambda snapshot, result: None,
    )
    try:
        worker.run_once()
    finally:
        logger.removeHandler(handler)

    assert jobs.finished[0][1] == expected
    entries = records(stream)
    assert {entry["job_id"] for entry in entries} == {str(job.id)}
    assert {entry["camera_id"] for entry in entries} == {str(job.camera_id)}
    failure = entries[-1]
    assert failure["level"] in {"WARNING", "ERROR"}
    assert "Traceback" in failure["exception"]
    assert_no_secrets(stream.getvalue())


def test_failure_stage_maps_taxonomy_and_unknown_codes():
    assert failure_stage("detector_inference_failed") == "DETECTOR"
    assert failure_stage("source_open_failed") == "SOURCE"
    assert failure_stage("storage_unavailable") == "STORAGE"
    assert failure_stage("worker_retries_exhausted") == "WORKER"
    assert failure_stage(None) == "WORKER"


class Recorder:
    def __init__(self):
        self.events = []

    def record_standalone(self, **kwargs):
        self.events.append(kwargs)
        return True


class Work:
    def __init__(self, camera):
        self.repositories = SimpleNamespace(
            cameras=SimpleNamespace(get=lambda _: camera),
            ai_configs=SimpleNamespace(active=lambda: SimpleNamespace()),
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class Runner:
    def __init__(self, steps):
        self.steps = steps

    def camera_pipeline(self, camera, config):
        return self.steps

    def search_components(self, config):
        return self.steps


def monitoring(steps, recorder, camera):
    return MonitoringService(
        lambda: Work(camera),
        health=SimpleNamespace(check=lambda: SimpleNamespace(components={})),
        search=SimpleNamespace(
            active_config=lambda: SimpleNamespace(
                encoder_name="rasa", encoder_version="v1", encoder_dimension=4
            )
        ),
        runtime=None,
        diagnostics=Runner(steps),
        audit=recorder,
    )


def test_failed_rtsp_diagnostic_is_audited_with_codes_only():
    camera = SimpleNamespace(
        id=uuid.uuid4(),
        status=CameraStatus.ACTIVE,
        ai_enabled=True,
        rtsp_url="rtsp://10.0.0.5/s",
        rtsp_credentials="gAAAA-secret",
    )
    steps = [
        Step("FRAME_SOURCE", "RTSP", Outcome.FAILED, "Không nhận được.", 5, "source_auth_failed"),
        Step("DETECTOR", "Detector", Outcome.SKIPPED, "Bỏ qua."),
    ]
    recorder = Recorder()
    actor = uuid.uuid4()

    monitoring(steps, recorder, camera).camera_pipeline(camera.id, actor_id=actor)

    [event] = recorder.events
    assert event["event_type"] is AuditEvent.AI_DIAGNOSTIC_FAILED
    assert event["result"] is AuditResult.FAILURE
    assert (event["target_type"], event["target_id"]) == ("camera", camera.id)
    assert event["actor_user_id"] == actor
    assert event["metadata"] == {
        "group": "camera_pipeline",
        "rtsp_source": True,
        "failed_components": [{"component": "FRAME_SOURCE", "code": "source_auth_failed"}],
    }
    assert "gAAAA" not in str(event) and "10.0.0.5" not in str(event)


def test_inconclusive_or_successful_diagnostics_are_not_audited():
    camera = SimpleNamespace(id=uuid.uuid4(), rtsp_url=None)
    recorder = Recorder()
    inconclusive = [Step("DETECTOR", "Detector", Outcome.INCONCLUSIVE, "Không có người.")]
    monitoring(inconclusive, recorder, camera).camera_pipeline(camera.id)
    monitoring([Step("TEXT_ENCODER", "T", Outcome.SUCCESS)], recorder, camera).search_components()
    assert recorder.events == []


def test_failed_search_component_diagnostic_is_audited():
    recorder = Recorder()
    steps = [Step("TEXT_ENCODER", "T", Outcome.FAILED, "lỗi", 1, "text_encoder_unavailable")]
    monitoring(steps, recorder, SimpleNamespace(id=None)).search_components(actor_id=None)
    [event] = recorder.events
    assert event["metadata"]["group"] == "search_components"
    assert event["target_type"] == "ai_search"


def test_business_searches_are_not_audited():
    from pathlib import Path

    root = Path(__file__).parents[2] / "src" / "person_search" / "services"
    for name in ("searches.py", "track_search.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "record_audit" not in source and "AuditEvent" not in source


def test_unhandled_api_error_hides_stack_and_secret_from_client():
    app = create_app({"TESTING": True, "ENVIRONMENT": "testing"})

    @app.get("/api/v1/_boom")
    def boom():
        raise RuntimeError("rtsp://admin:hunter2@10.0.0.5/s")

    logger, handler, stream = capture("person_search.api.errors")
    try:
        response = app.test_client().get(
            "/api/v1/_boom", headers={"X-Request-ID": "req-abcdef12"}
        )
    finally:
        logger.removeHandler(handler)

    body = response.get_json()
    assert response.status_code == 500
    assert body["error"] == {
        "code": "internal_error",
        "message": "Đã xảy ra lỗi hệ thống.",
        "request_id": "req-abcdef12",
    }
    assert "Traceback" not in response.get_data(as_text=True)
    [entry] = records(stream)
    assert entry["request_id"] == "req-abcdef12"
    assert "Traceback" in entry["exception"]
    assert_no_secrets(stream.getvalue())
    assert current_context() == {}
