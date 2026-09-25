"""In-memory smoke coverage for the explicitly selected demo worker path."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.storage.postgres.models import (
    AIConfigVersion,
    Camera,
    JobStatus,
    TrackIndexStatus,
)
from person_search.workers.pipeline import Pipeline, SourceFrame
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
    def __init__(self, job, config, area_id):
        self.job = job
        self.factory = lambda: nullcontext(SimpleNamespace(session=_Session(config, area_id)))
        self.staging = SimpleNamespace(path=lambda source_ref: source_ref)
        self.finished = []
        self.checkpoints = []

    def cleanup(self):
        return None

    def claim(self):
        job, self.job = self.job, None
        return job

    def checkpoint(self, job_id, lease_token, processed, sampled):
        self.checkpoints.append((processed, sampled))
        return True

    def finish(self, job_id, lease_token, status, error_code=None):
        self.finished.append((status, error_code))


class _Source:
    def frames(self, source, sampling):
        assert source == "memory://fixture"
        assert sampling == 10
        image = Image.new("RGB", (64, 48), "red")
        for index in range(5):
            yield SourceFrame(index=index, timestamp_ms=index * 400, image=image.copy())


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
        checkpoint_sha256="0" * 64,
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
    worker = VideoWorker(
        _Engine(),
        jobs,
        Pipeline.demo,
        lambda active_config: ingestion,
        source=_Source(),
    )

    assert worker.run_once() is True
    assert jobs.finished == [(JobStatus.SUCCEEDED, None)]
    assert jobs.checkpoints[-1] == (5, 5)
    assert len(ingestion.requests) == 1
    request = ingestion.requests[0]
    assert request.processing_job_id == job.id
    assert request.source_frame_index == 0
    assert request.source_started_at_ms == 0
    assert request.source_ended_at_ms == 1600
    assert request.encoder.version == "fake_demo_v1"
    assert len(request.embedding) == 256
    assert request.frame_bytes.startswith(b"\xff\xd8")
