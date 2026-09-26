from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from person_search.storage.postgres.models import JobSourceType, JobStatus
from person_search.workers.durable import SequentialProductionWorker
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipelineResult
from person_search.workers.production_main import PublisherNotConfigured, _supervise_child

pytestmark = pytest.mark.unit


class Lock:
    def __init__(self, acquired=True):
        self.acquired = acquired

    def __enter__(self):
        return self.acquired

    def __exit__(self, *args):
        return None


class Source:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        return iter(())


class Pipeline:
    def __init__(self, progress, *, error=None, stop_after_progress=None):
        self.progress = progress
        self.error = error
        self.stop_after_progress = stop_after_progress

    def run(self, source):
        del source
        self.progress(10, 1, 0)
        if self.stop_after_progress:
            self.stop_after_progress()
        if self.error:
            raise self.error
        self.progress(20, 2, 1)
        return ProductionPipelineResult(20, 2, 3, 4, (), ())


class Jobs:
    def __init__(self, jobs, *, lose_lease_at=None):
        self.queue = list(jobs)
        self.finished = []
        self.checkpoints = []
        self.cleaned = 0
        self.lose_lease_at = lose_lease_at

    def cleanup(self):
        self.cleaned += 1

    def claim(self):
        return self.queue.pop(0) if self.queue else None

    def checkpoint(self, job_id, token, processed, sampled, completed, published):
        self.checkpoints.append((processed, sampled, completed, published))
        return self.lose_lease_at is None or len(self.checkpoints) < self.lose_lease_at

    def finish(self, job_id, token, status, error_code=None):
        self.finished.append((job_id, status, error_code))


def job(*, attempts=1, source_type=JobSourceType.FILE):
    return SimpleNamespace(
        id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        source_type=source_type,
        source_ref="fixture.mp4",
        sampling_interval=10,
        timeline_origin_utc=datetime(2026, 9, 26, tzinfo=UTC),
        attempts=attempts,
    )


def worker(jobs, *, acquired=True, stop=lambda: False, pipeline_error=None):
    sources = []

    def source_factory(snapshot):
        source = Source()
        sources.append(source)
        return source

    subject = SequentialProductionWorker(
        jobs,
        lock_factory=lambda: Lock(acquired),
        source_factory=source_factory,
        pipeline_factory=lambda snapshot, cancelled, progress: Pipeline(
            progress, error=pipeline_error
        ),
        result_consumer=lambda snapshot, result: None,
        stop=stop,
    )
    return subject, sources


def test_seven_jobs_run_sequentially_with_snapshots_and_progress():
    claimed = [job() for _ in range(7)]
    jobs = Jobs(claimed)
    subject, sources = worker(jobs)

    assert subject.run_until_idle() == 7
    assert [item[0] for item in jobs.finished] == [item.id for item in claimed]
    assert all(item[1] is JobStatus.SUCCEEDED for item in jobs.finished)
    assert len(sources) == 7 and all(source.closed for source in sources)
    assert jobs.cleaned == 8  # One final idle poll is also reconciled.
    assert (20, 2, 1, 0) in jobs.checkpoints


def test_global_lock_prevents_claiming_a_second_worker():
    pending = job()
    jobs = Jobs([pending])
    subject, _ = worker(jobs, acquired=False)
    assert subject.run_once() is False
    assert jobs.queue == [pending]
    assert jobs.finished == []


def test_lease_loss_cancels_without_consuming_more_work():
    claimed = job()
    jobs = Jobs([claimed], lose_lease_at=2)
    subject, sources = worker(jobs)
    assert subject.run_once() is True
    assert jobs.finished == [(claimed.id, JobStatus.CANCELLED, None)]
    assert sources[0].closed


def test_graceful_stop_leaves_running_job_for_lease_recovery():
    claimed = job()
    state = {"stop": False}
    jobs = Jobs([claimed])
    sources = []

    def source_factory(snapshot):
        source = Source()
        sources.append(source)
        return source

    def pipeline_factory(snapshot, cancelled, progress):
        return Pipeline(progress, stop_after_progress=lambda: state.update(stop=True))

    subject = SequentialProductionWorker(
        jobs,
        lock_factory=Lock,
        source_factory=source_factory,
        pipeline_factory=pipeline_factory,
        result_consumer=lambda snapshot, result: None,
        stop=lambda: state["stop"],
    )
    assert subject.run_once() is True
    assert jobs.finished == []
    assert sources[0].closed


def test_retry_limit_and_invalid_job_fail_safely():
    exhausted = job(attempts=4)
    invalid = job(source_type=JobSourceType.RTSP)
    jobs = Jobs([exhausted, invalid])
    subject, _ = worker(jobs)
    assert subject.run_until_idle(max_jobs=2) == 2
    assert jobs.finished[0] == (
        exhausted.id,
        JobStatus.FAILED,
        "worker_retries_exhausted",
    )
    assert jobs.finished[1] == (
        invalid.id,
        JobStatus.FAILED,
        "worker_execution_failed",
    )


def test_ai_stage_error_is_persisted_without_internal_details():
    claimed = job()
    jobs = Jobs([claimed])
    error = AIWorkerError(
        AIErrorCode.DETECTOR_INFERENCE_FAILED, internal_detail="secret model path"
    )
    subject, _ = worker(jobs, pipeline_error=error)
    assert subject.run_once() is True
    assert jobs.finished == [
        (claimed.id, JobStatus.FAILED, AIErrorCode.DETECTOR_INFERENCE_FAILED.value)
    ]


def test_missing_aiw18_publisher_fails_closed_instead_of_succeeding():
    claimed = job()
    jobs = Jobs([claimed])
    subject, _ = worker(jobs)
    subject.result_consumer = PublisherNotConfigured()
    assert subject.run_once() is True
    assert jobs.finished == [
        (claimed.id, JobStatus.FAILED, AIErrorCode.STORAGE_UNAVAILABLE.value)
    ]


def test_supervisor_terminates_child_promptly_on_graceful_stop(monkeypatch):
    child = SimpleNamespace(
        poll=Mock(return_value=None),
        terminate=Mock(),
        kill=Mock(),
        wait=Mock(return_value=0),
    )
    monkeypatch.setattr(
        "person_search.workers.production_main.subprocess.Popen", lambda *args, **kwargs: child
    )

    class StopEvent:
        def __init__(self):
            self.stopped = False

        def wait(self, seconds):
            self.stopped = True
            return True

        def is_set(self):
            return self.stopped

    _supervise_child(StopEvent(), 60)
    child.terminate.assert_called_once()
    child.kill.assert_not_called()
