"""In-memory smoke coverage for the explicitly selected demo worker path."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.demo import DEMO_ENCODER_SHA256, build_demo_pipeline
from person_search.storage.postgres.models import (
    AIConfigVersion,
    Camera,
    JobStatus,
    TrackIndexStatus,
)
from person_search.workers.contracts import SampledFrame, SourceFrame
from person_search.workers.runner import VideoWorker

pytestmark = pytest.mark.unit


class _Guard:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def scalar(self, statement, parameters):
        return True

    def execute(self, statement, parameters=None):
        return None

    def commit(self):
        return None


class _Engine:
    def connect(self):
        return _Guard()


class _Session:
    def __init__(self, config, area_id):
        self.config = config
        self.area_id = area_id

    def get(self, model, identity):
        if model is AIConfigVersion:
            return self.config
        if model is Camera:
            return SimpleNamespace(area_id=self.area_id)
        raise AssertionError(f"Unexpected model lookup: {model}")


class _Jobs:
    def __init__(self, job, config, area_id, cancel_at_processed=None):
        self.job = job
        self.factory = lambda: nullcontext(SimpleNamespace(session=_Session(config, area_id)))
        self.staging = SimpleNamespace(path=lambda source_ref: source_ref)
        self.finished = []
        self.checkpoints = []
        self.cancel_at_processed = cancel_at_processed

    def cleanup(self):
        return None

    def claim(self):
        job, self.job = self.job, None
        return job

    def checkpoint(self, job_id, lease_token, processed, sampled):
        self.checkpoints.append((processed, sampled))
        return self.cancel_at_processed is None or processed < self.cancel_at_processed

    def finish(self, job_id, lease_token, status, error_code=None):
        self.finished.append((status, error_code))


class _Source:
    def frames(self, source, sampling, camera_id):
        assert source == "memory://fixture"
        assert sampling == 10
        image = Image.new("RGB", (64, 48), "red")
        for index in range(41):
            yield SourceFrame(
                camera_id=camera_id,
                source_frame_index=index,
                source_timestamp_ms=index * 40,
                image=image.copy(),
                width=64,
                height=48,
            )


class _Ingestion:
    def __init__(self):
        self.requests = []

    def ingest_track(self, request):
        self.requests.append(request)
        return SimpleNamespace(status=TrackIndexStatus.READY)


def test_demo_worker_smoke_uses_memory_only_and_completes_one_track():
    config = SimpleNamespace(
        detector_name="demo_detector",
        detector_version="1",
        tracker_name="demo_tracker",
        tracker_version="1",
        encoder_name="demo_encoder",
        encoder_version="fake_demo_v1",
        encoder_dimension=256,
        checkpoint_sha256=DEMO_ENCODER_SHA256,
    )
    job = SimpleNamespace(
        id=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        timeline_origin_utc=datetime(2026, 9, 25, tzinfo=UTC),
        source_ref="memory://fixture",
        sampling_interval=10,
        lease_token=uuid.uuid4(),
        attempts=1,
    )
    jobs = _Jobs(job, config, uuid.uuid4())
    ingestion = _Ingestion()
    pipeline = build_demo_pipeline(config)
    detector = pipeline.detector.detect
    detected_indices = []

    def detect(frame):
        assert isinstance(frame, SampledFrame)
        detected_indices.append(frame.source_frame_index)
        return detector(frame)

    pipeline.detector.detect = detect
    worker = VideoWorker(
        _Engine(),
        jobs,
        lambda active_config: pipeline,
        lambda active_config: ingestion,
        source=_Source(),
    )

    assert worker.run_once() is True
    assert jobs.finished == [(JobStatus.SUCCEEDED, None)]
    assert jobs.checkpoints[-1] == (41, 5)
    assert detected_indices == [0, 10, 20, 30, 40]
    assert len(ingestion.requests) == 1
    request = ingestion.requests[0]
    assert request.processing_job_id == job.id
    assert request.source_frame_index == 0
    assert request.source_started_at_ms == 0
    assert request.source_ended_at_ms == 1600
    assert request.encoder.version == "fake_demo_v1"
    assert request.synthetic_metadata.synthetic is True
    assert request.synthetic_metadata.fixture_id == "central-person-v1"
    assert len(request.embedding) == 256
    assert request.frame_bytes.startswith(b"\xff\xd8")


def test_worker_cancellation_stops_before_detector_receives_another_frame():
    config = SimpleNamespace(
        detector_name="demo_detector",
        detector_version="1",
        tracker_name="demo_tracker",
        tracker_version="1",
        encoder_name="demo_encoder",
        encoder_version="fake_demo_v1",
        encoder_dimension=256,
        checkpoint_sha256=DEMO_ENCODER_SHA256,
    )
    job = SimpleNamespace(
        id=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        timeline_origin_utc=datetime(2026, 9, 25, tzinfo=UTC),
        source_ref="memory://fixture",
        sampling_interval=10,
        lease_token=uuid.uuid4(),
        attempts=1,
    )
    jobs = _Jobs(job, config, uuid.uuid4(), cancel_at_processed=2)
    pipeline = build_demo_pipeline(config)
    detector = pipeline.detector.detect
    detected_indices = []

    def detect(frame):
        detected_indices.append(frame.source_frame_index)
        return detector(frame)

    pipeline.detector.detect = detect
    worker = VideoWorker(
        _Engine(),
        jobs,
        lambda active_config: pipeline,
        lambda active_config: _Ingestion(),
        source=_Source(),
    )

    assert worker.run_once() is True
    assert jobs.finished == [(JobStatus.CANCELLED, None)]
    assert detected_indices == [0]
