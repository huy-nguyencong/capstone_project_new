from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.api.errors import ApiError
from person_search.storage.postgres.models import JobSourceType, JobStatus
from person_search.workers.contracts import SourceFrame
from person_search.workers.durable import (
    BudgetedSource,
    JobExecutionSnapshot,
    SequentialProductionWorker,
    rtsp_source_factory,
    source_factory_by_type,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipelineResult

pytestmark = pytest.mark.unit


def claimed(**overrides):
    values = dict(
        id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        source_type=JobSourceType.RTSP,
        source_ref=None,
        sampling_interval=10,
        timeline_origin_utc=datetime(2026, 9, 26, tzinfo=UTC),
        attempts=1,
        total_frames=300,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_rtsp_snapshot_requires_positive_frame_budget():
    snapshot = JobExecutionSnapshot.from_claimed(claimed())
    assert snapshot.source_type is JobSourceType.RTSP
    assert snapshot.frame_budget == 300 and snapshot.source_ref is None
    for budget in (None, 0, -1):
        with pytest.raises(ValueError):
            JobExecutionSnapshot.from_claimed(claimed(total_frames=budget))
    file_snapshot = JobExecutionSnapshot.from_claimed(
        claimed(source_type=JobSourceType.FILE, source_ref="clip.mp4", total_frames=None)
    )
    assert file_snapshot.frame_budget is None
    with pytest.raises(ValueError):
        JobExecutionSnapshot.from_claimed(claimed(source_type=JobSourceType.FILE))


class Stream:
    def __init__(self, count=10, reconnects=2):
        self.count = count
        self.reconnects = reconnects
        self.images = []
        self.entered = self.exited = False
        self.opened_with = None

    def open(self, url, *, camera_id):
        self.opened_with = (url, camera_id)
        return self

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *args):
        self.exited = True

    def __iter__(self):
        camera = uuid.uuid4()
        for index in range(self.count):
            image = Image.new("RGB", (4, 4))
            self.images.append(image)
            yield SourceFrame(camera, index, index * 40, image, 4, 4)


def closed(image):
    try:
        image.getpixel((0, 0))
    except ValueError:
        return True
    return False


def test_budgeted_source_stops_at_budget_and_exposes_reconnects():
    stream = Stream(count=10, reconnects=3)
    with BudgetedSource(stream, 4) as source:
        frames = list(source)
    assert len(frames) == 4 and source.reconnects == 3
    assert closed(stream.images[4]) and len(stream.images) == 5
    assert stream.entered and stream.exited
    assert len(list(BudgetedSource(Stream(count=3), None))) == 3


def test_rtsp_factory_decrypts_through_resolver_and_applies_budget():
    stream = Stream()
    created = {}

    def source_class(**kwargs):
        created.update(kwargs)
        return stream

    resolver = object()
    factory = rtsp_source_factory(
        lambda camera_id: ("rtsp://10.0.0.5/live", "encrypted"),
        resolver,
        source_class=source_class,
        max_reconnects=5,
    )
    snapshot = JobExecutionSnapshot.from_claimed(claimed(total_frames=2))

    source = factory(snapshot)

    assert created == {
        "encrypted_secret": "encrypted",
        "access_resolver": resolver,
        "max_reconnects": 5,
    }
    assert stream.opened_with == ("rtsp://10.0.0.5/live", snapshot.camera_id)
    assert isinstance(source, BudgetedSource) and source.budget == 2


@pytest.mark.parametrize(
    ("loader", "error"),
    [
        (lambda camera_id: (None, None), None),
        (
            lambda camera_id: ("rtsp://127.0.0.1/live", None),
            ApiError(422, "rtsp_host_forbidden", "blocked"),
        ),
        (lambda camera_id: ("rtsp://10.0.0.5/live", None), RuntimeError("rtsp://u:p@h")),
    ],
)
def test_rtsp_factory_maps_open_failures_to_source_taxonomy(loader, error):
    class Failing:
        def __init__(self, **kwargs):
            pass

        def open(self, url, *, camera_id):
            raise error

    factory = rtsp_source_factory(loader, lambda *args: None, source_class=Failing)
    with pytest.raises(AIWorkerError) as caught:
        factory(JobExecutionSnapshot.from_claimed(claimed()))
    assert caught.value.code is AIErrorCode.SOURCE_OPEN_FAILED
    assert "u:p" not in str(caught.value)


def test_source_factory_dispatches_by_job_type():
    rtsp = JobExecutionSnapshot.from_claimed(claimed())
    file = JobExecutionSnapshot.from_claimed(
        claimed(source_type=JobSourceType.FILE, source_ref="clip.mp4")
    )
    factory = source_factory_by_type(lambda s: ("file", s.source_ref), lambda s: ("rtsp", None))
    assert factory(rtsp) == ("rtsp", None)
    assert factory(file) == ("file", "clip.mp4")
    with pytest.raises(AIWorkerError):
        source_factory_by_type(lambda s: None)(rtsp)


class Lock:
    def __enter__(self):
        return True

    def __exit__(self, *args):
        return None


class Jobs:
    def __init__(self, job):
        self.queue = [job]
        self.finished = []
        self.deferred = []

    def cleanup(self):
        return None

    def claim(self):
        return self.queue.pop(0) if self.queue else None

    def checkpoint(self, *args, **kwargs):
        return True

    def finish(self, job_id, token, status, error_code=None):
        self.finished.append((status, error_code))

    def defer_retry(self, *args):
        self.deferred.append(args)
        return True


def worker(jobs, *, error=None, frames=None):
    class Pipeline:
        def __init__(self, progress):
            self.progress = progress

        def run(self, source):
            count = 0
            for frame in source:
                frame.image.close()
                count += 1
            if error is not None:
                raise error
            return ProductionPipelineResult(count, count // 10, 0, 0, (), ())

    return SequentialProductionWorker(
        jobs,
        lock_factory=Lock,
        source_factory=lambda snapshot: BudgetedSource(
            Stream(count=frames or 50), snapshot.frame_budget
        ),
        pipeline_factory=lambda snapshot, cancelled, progress: Pipeline(progress),
        result_consumer=lambda snapshot, result: None,
    )


def test_rtsp_job_succeeds_within_frame_budget():
    jobs = Jobs(claimed(total_frames=20))
    assert worker(jobs).run_once()
    assert jobs.finished == [(JobStatus.SUCCEEDED, None)]


def test_retryable_rtsp_failure_is_not_replayed_on_a_new_stream():
    jobs = Jobs(claimed())
    worker(jobs, error=AIWorkerError(AIErrorCode.SOURCE_READ_TIMEOUT)).run_once()
    assert jobs.deferred == []
    assert jobs.finished == [(JobStatus.FAILED, AIErrorCode.SOURCE_READ_TIMEOUT.value)]


def test_reclaimed_rtsp_session_fails_explicitly():
    jobs = Jobs(claimed(attempts=2))
    worker(jobs).run_once()
    assert jobs.finished == [(JobStatus.FAILED, "rtsp_session_interrupted")]
