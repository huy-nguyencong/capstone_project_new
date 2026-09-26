from __future__ import annotations

import gc
import logging
import uuid
import weakref
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from person_search.ai.selectors import RepresentativeFrameSelector, SelectorSettings
from person_search.services.track_ingestion import TrackIngestionConflictError
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.postgres.models import JobSourceType, JobStatus, TrackIndexStatus
from person_search.workers.contracts import (
    Detection,
    EmbeddingVector,
    ModelLineage,
    SourceFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.durable import SequentialProductionWorker
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipeline
from person_search.workers.publication import ProductionTrackPublisher

pytestmark = [pytest.mark.unit, pytest.mark.failure_injection]

SHA = "d" * 64
DETECTOR = ModelLineage("detector", "1", SHA)
TRACKER = ModelLineage("tracker", "1", SHA)
ENCODER = ModelLineage("encoder", "encoder_v1", SHA)
DIMENSION = 8


def fresh(error):
    if isinstance(error, AIWorkerError):
        return AIWorkerError(error.code)
    return error


class Registry:
    def __init__(self):
        self.images = []
        self.components = []

    def image(self, width=80, height=100):
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        for x in range(0, width, 4):
            draw.line((x, 0, x, height - 1), fill="black")
        self.images.append(image)
        return image

    def open_images(self):
        count = 0
        for image in self.images:
            try:
                image.getpixel((0, 0))
            except ValueError:
                continue
            count += 1
        return count


class Component:
    def __init__(self, registry, *, open_error=None):
        self.registry = registry
        self.open_error = open_error
        self.opened = False
        self.closed = False
        registry.components.append(self)

    def open(self):
        if self.open_error is not None:
            raise self.open_error
        self.opened = True

    def close(self):
        self.closed = True


class Detector(Component):
    lineage = DETECTOR

    def __init__(self, registry, *, error=None, fail_at=0, **kwargs):
        super().__init__(registry, **kwargs)
        self.error = error
        self.fail_at = fail_at
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        if self.error is not None and self.calls > self.fail_at:
            raise fresh(self.error)
        return (
            Detection(
                BoundingBoxPixels(15, 10, 30, 70, frame.width, frame.height),
                0,
                "person",
                0.9,
                DETECTOR,
            ),
        )


class Tracker(Component):
    lineage = TRACKER

    def __init__(self, registry, *, error=None, flush_error=None, **kwargs):
        super().__init__(registry, **kwargs)
        self.error = error
        self.flush_error = flush_error
        self.last = None

    def update(self, frame, detections):
        if self.error is not None:
            raise self.error
        self.last = frame
        return tuple(
            TrackUpdate(
                "track-1",
                frame.camera_id,
                item.bbox,
                frame.source_frame_index,
                frame.source_timestamp_ms,
                TrackState.ACTIVE,
                TRACKER,
            )
            for item in detections[:1]
        )

    def flush(self):
        if self.flush_error is not None:
            raise self.flush_error
        if self.last is None:
            return ()
        return (
            TrackUpdate(
                "track-1",
                self.last.camera_id,
                BoundingBoxPixels(15, 10, 30, 70, self.last.width, self.last.height),
                self.last.source_frame_index,
                self.last.source_timestamp_ms,
                TrackState.ENDED,
                TRACKER,
            ),
        )


class Encoder(Component):
    lineage = ENCODER

    def __init__(self, registry, *, error=None, values=None, **kwargs):
        super().__init__(registry, **kwargs)
        self.error = error
        self.values = values

    def encode(self, crop):
        if self.error is not None:
            raise self.error
        values = self.values or (1.0,) + (0.0,) * (DIMENSION - 1)
        return EmbeddingVector(values, DIMENSION, True, ENCODER)


class Source:
    def __init__(self, registry, camera_id, *, count=4, error_after=None, error=None):
        self.registry = registry
        self.camera_id = camera_id
        self.count = count
        self.error_after = error_after
        self.error = error or AIWorkerError(AIErrorCode.SOURCE_READ_FAILED)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        for index in range(self.count):
            if self.error_after is not None and index >= self.error_after:
                raise self.error
            yield SourceFrame(
                self.camera_id, index, index * 40, self.registry.image(), 80, 100
            )


class Jobs:
    def __init__(self, claimed, *, lose_lease_at=None):
        self.queue = list(claimed)
        self.finished = []
        self.deferred = []
        self.checkpoints = 0
        self.lose_lease_at = lose_lease_at

    def cleanup(self):
        return None

    def claim(self):
        return self.queue.pop(0) if self.queue else None

    def checkpoint(self, *args, **kwargs):
        self.checkpoints += 1
        return self.lose_lease_at is None or self.checkpoints < self.lose_lease_at

    def finish(self, job_id, token, status, error_code=None):
        self.finished.append((job_id, status, error_code))

    def defer_retry(self, job_id, token, error_code, delay):
        self.deferred.append((job_id, error_code))
        return True


class Ingestion:
    def __init__(self, *, error=None, status=TrackIndexStatus.READY):
        self.error = error
        self.status = status
        self.requests = []

    def ingest_track(self, request, *, correlation_id=None):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(status=self.status)


def claimed(attempts=1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        source_type=JobSourceType.FILE,
        source_ref="clip.mp4",
        sampling_interval=1,
        timeline_origin_utc=datetime(2026, 9, 26, tzinfo=UTC),
        attempts=attempts,
    )


class Harness:
    def __init__(
        self,
        jobs,
        *,
        detector=None,
        tracker=None,
        encoder=None,
        source=None,
        ingestion=None,
        stop=lambda: False,
    ):
        self.registry = Registry()
        self.jobs = jobs
        self.detector_options = detector or {}
        self.tracker_options = tracker or {}
        self.encoder_options = encoder or {}
        self.source_options = source or {}
        self.ingestion = ingestion or Ingestion()
        self.sources = []
        self.pipelines = []
        self.worker = SequentialProductionWorker(
            jobs,
            lock_factory=Lock,
            source_factory=self.source_factory,
            pipeline_factory=self.pipeline_factory,
            result_consumer=ProductionTrackPublisher(self.ingestion, uuid.uuid4(), jobs),
            stop=stop,
        )

    def source_factory(self, snapshot):
        source = Source(self.registry, snapshot.camera_id, **self.source_options)
        self.sources.append(source)
        return source

    def pipeline_factory(self, snapshot, cancelled, progress):
        selector = RepresentativeFrameSelector(
            processing_job_id=snapshot.job_id,
            ai_config_version_id=snapshot.ai_config_version_id,
            detector=DETECTOR,
            tracker=TRACKER,
            encoder=ENCODER,
            settings=SelectorSettings(
                minimum_bbox_width=8,
                minimum_bbox_height=8,
                minimum_sharpness_variance=0.01,
            ),
        )
        pipeline = ProductionPipeline(
            Detector(self.registry, **self.detector_options),
            Tracker(self.registry, **self.tracker_options),
            selector,
            Encoder(self.registry, **self.encoder_options),
            sampling_interval=snapshot.sampling_interval,
            job_timeout_seconds=30,
            cancelled=cancelled,
            progress=progress,
        )
        self.pipelines.append(weakref.ref(pipeline))
        return pipeline

    def assert_clean(self):
        assert self.registry.open_images() == 0
        assert all(
            component.closed or not component.opened for component in self.registry.components
        )
        assert all(source.closed for source in self.sources)


class Lock:
    def __enter__(self):
        return True

    def __exit__(self, *args):
        return None


def test_happy_path_publishes_and_releases_every_frame():
    job = claimed()
    jobs = Jobs([job])
    harness = Harness(jobs)

    assert harness.worker.run_once()

    assert jobs.finished == [(job.id, JobStatus.SUCCEEDED, None)]
    assert len(harness.ingestion.requests) == 1
    request = harness.ingestion.requests[0]
    assert request.frame_bytes[:2] == b"\xff\xd8"
    assert len(request.embedding) == DIMENSION
    harness.assert_clean()


@pytest.mark.parametrize(
    ("options", "expected_status", "expected_code"),
    [
        (
            {"source": {"error_after": 2}},
            "deferred",
            AIErrorCode.SOURCE_READ_FAILED.value,
        ),
        (
            {
                "source": {
                    "error_after": 0,
                    "error": AIWorkerError(AIErrorCode.SOURCE_INVALID_FRAME),
                }
            },
            JobStatus.FAILED,
            AIErrorCode.SOURCE_INVALID_FRAME.value,
        ),
        (
            {"detector": {"open_error": AIWorkerError(AIErrorCode.DETECTOR_UNAVAILABLE)}},
            "deferred",
            AIErrorCode.DETECTOR_UNAVAILABLE.value,
        ),
        (
            {
                "detector": {
                    "error": AIWorkerError(AIErrorCode.DETECTOR_OUTPUT_INVALID),
                    "fail_at": 2,
                }
            },
            JobStatus.FAILED,
            AIErrorCode.DETECTOR_OUTPUT_INVALID.value,
        ),
        (
            {"tracker": {"error": AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID)}},
            JobStatus.FAILED,
            AIErrorCode.TRACKER_OUTPUT_INVALID.value,
        ),
        (
            {"tracker": {"flush_error": AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED)}},
            "deferred",
            AIErrorCode.TRACKER_INFERENCE_FAILED.value,
        ),
        (
            {"encoder": {"error": AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED)}},
            "deferred",
            AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED.value,
        ),
        (
            {"encoder": {"error": AIWorkerError(AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID)}},
            JobStatus.FAILED,
            AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID.value,
        ),
        (
            {"encoder": {"error": MemoryError()}},
            JobStatus.FAILED,
            "worker_execution_failed",
        ),
        (
            {"ingestion": Ingestion(error=ConnectionError("minio down"))},
            "deferred",
            AIErrorCode.STORAGE_UNAVAILABLE.value,
        ),
        (
            {"ingestion": Ingestion(error=TrackIngestionConflictError("duplicate"))},
            JobStatus.FAILED,
            AIErrorCode.STORAGE_CONFLICT.value,
        ),
        (
            {"ingestion": Ingestion(status=TrackIndexStatus.PENDING)},
            "deferred",
            AIErrorCode.STORAGE_PUBLISH_FAILED.value,
        ),
    ],
)
def test_injected_failure_maps_to_taxonomy_and_cleans_up(options, expected_status, expected_code):
    job = claimed()
    jobs = Jobs([job])
    harness = Harness(jobs, **options)

    assert harness.worker.run_once()

    if expected_status == "deferred":
        assert jobs.finished == []
        assert jobs.deferred == [(job.id, expected_code)]
    else:
        assert jobs.deferred == []
        assert jobs.finished == [(job.id, expected_status, expected_code)]
    harness.assert_clean()


def test_retryable_failure_at_last_attempt_is_dead_lettered():
    job = claimed(attempts=3)
    jobs = Jobs([job])
    harness = Harness(
        jobs, encoder={"error": AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED)}
    )

    harness.worker.run_once()

    assert jobs.finished == [(job.id, JobStatus.FAILED, "worker_retries_exhausted")]
    harness.assert_clean()


@pytest.mark.parametrize("lose_at", [2, 3, 5])
def test_lease_loss_or_cancel_at_any_checkpoint_cancels_and_cleans_up(lose_at):
    job = claimed()
    jobs = Jobs([job], lose_lease_at=lose_at)
    harness = Harness(jobs)

    harness.worker.run_once()

    assert jobs.finished == [(job.id, JobStatus.CANCELLED, None)]
    harness.assert_clean()


def test_lease_loss_during_publication_cancels_without_extra_tracks():
    job = claimed()
    harness_jobs = Jobs([job])
    harness = Harness(harness_jobs)
    total = None

    def probe():
        nonlocal total
        before = harness_jobs.checkpoints
        harness.worker.run_once()
        total = harness_jobs.checkpoints - before

    probe()
    job = claimed()
    jobs = Jobs([job], lose_lease_at=total)
    harness = Harness(jobs)

    harness.worker.run_once()

    assert jobs.finished[-1][1] is JobStatus.CANCELLED
    assert len(harness.ingestion.requests) <= 1
    harness.assert_clean()


def test_graceful_stop_mid_job_leaves_lease_for_recovery_and_cleans_up():
    job = claimed()
    jobs = Jobs([job])
    calls = {"count": 0}

    def stop():
        calls["count"] += 1
        return calls["count"] > 3

    harness = Harness(jobs, stop=stop)

    assert harness.worker.run_once()

    assert jobs.finished == [] and jobs.deferred == []
    harness.assert_clean()


def test_repeated_jobs_release_frames_components_and_pipelines():
    jobs = Jobs([claimed() for _ in range(25)])
    harness = Harness(jobs, source={"count": 6})

    assert harness.worker.run_until_idle() == 25

    assert [item[1] for item in jobs.finished] == [JobStatus.SUCCEEDED] * 25
    assert len(harness.registry.images) == 25 * 6
    harness.assert_clean()
    gc.collect()
    assert all(reference() is None for reference in harness.pipelines)


def test_repeated_failing_jobs_do_not_leak_frames(monkeypatch):
    monkeypatch.setattr(logging.getLogger("person_search.workers.durable"), "disabled", True)
    gc.collect()
    jobs = Jobs([claimed() for _ in range(10)])
    harness = Harness(
        jobs,
        detector={"error": AIWorkerError(AIErrorCode.DETECTOR_OUTPUT_INVALID), "fail_at": 3},
        source={"count": 6},
    )

    assert harness.worker.run_until_idle() == 10

    assert {item[2] for item in jobs.finished} == {AIErrorCode.DETECTOR_OUTPUT_INVALID.value}
    harness.assert_clean()
    gc.collect()
    assert all(reference() is None for reference in harness.pipelines)
