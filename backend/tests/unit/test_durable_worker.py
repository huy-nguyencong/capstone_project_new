from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from person_search.storage.postgres.models import JobSourceType, JobStatus
from person_search.workers.durable import SequentialProductionWorker, WorkerRetryPolicy
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipelineResult, StageTiming
from person_search.workers.production_main import PublisherNotConfigured, _supervise_child
from person_search.workers.telemetry import WorkerRunState

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
        self.deferred = []
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

    def defer_retry(self, job_id, token, error_code, delay):
        self.deferred.append((job_id, error_code, delay.total_seconds()))
        return True


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


def test_retryable_ai_stage_error_is_deferred_with_bounded_backoff():
    claimed = job()
    jobs = Jobs([claimed])
    error = AIWorkerError(
        AIErrorCode.DETECTOR_INFERENCE_FAILED, internal_detail="secret model path"
    )
    subject, _ = worker(jobs, pipeline_error=error)
    assert subject.run_once() is True
    assert jobs.finished == []
    assert jobs.deferred == [
        (claimed.id, AIErrorCode.DETECTOR_INFERENCE_FAILED.value, 5.0)
    ]


def test_terminal_ai_stage_error_fails_without_retry():
    claimed = job()
    jobs = Jobs([claimed])
    error = AIWorkerError(AIErrorCode.DETECTOR_OUTPUT_INVALID)
    subject, _ = worker(jobs, pipeline_error=error)
    assert subject.run_once() is True
    assert jobs.deferred == []
    assert jobs.finished == [
        (claimed.id, JobStatus.FAILED, AIErrorCode.DETECTOR_OUTPUT_INVALID.value)
    ]


def test_retryable_error_at_attempt_limit_moves_to_dead_letter_code():
    claimed = job(attempts=3)
    jobs = Jobs([claimed])
    subject, _ = worker(
        jobs, pipeline_error=AIWorkerError(AIErrorCode.STORAGE_UNAVAILABLE)
    )
    assert subject.run_once() is True
    assert jobs.deferred == []
    assert jobs.finished == [
        (claimed.id, JobStatus.FAILED, "worker_retries_exhausted")
    ]


def test_worker_retry_backoff_is_exponential_and_capped():
    policy = WorkerRetryPolicy(
        max_attempts=5, base_delay_seconds=2, max_delay_seconds=5
    )
    assert [policy.delay_after(value).total_seconds() for value in (1, 2, 3, 10)] == [
        2,
        4,
        5,
        5,
    ]


def test_storage_unavailable_publisher_is_deferred_instead_of_succeeding():
    claimed = job()
    jobs = Jobs([claimed])
    subject, _ = worker(jobs)
    subject.result_consumer = PublisherNotConfigured()
    assert subject.run_once() is True
    assert jobs.finished == []
    assert jobs.deferred == [
        (claimed.id, AIErrorCode.STORAGE_UNAVAILABLE.value, 5.0)
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


class MetricJobs(Jobs):
    def __init__(self, jobs, **kwargs):
        super().__init__(jobs, **kwargs)
        self.metrics = []

    def checkpoint(self, job_id, token, processed, sampled, completed, published, **kwargs):
        if "metrics" in kwargs:
            self.metrics.append((processed, sampled, completed, kwargs["metrics"]))
        return super().checkpoint(job_id, token, processed, sampled, completed, published)


class TimedPipeline(Pipeline):
    def stage_timings(self):
        return (StageTiming("detector", 2, 30.0),)


class Collector:
    def __init__(self):
        self.attached = None
        self.snapshots = 0

    def attach(self, timings):
        self.attached = timings

    def due(self):
        return False

    def snapshot(self, source_frames, sampled_frames, completed_tracks):
        self.snapshots += 1
        return {"source_fps": float(source_frames), "track_count": float(completed_tracks)}


class Heartbeat:
    def __init__(self):
        self.events = []

    def busy(self, job_id):
        self.events.append(("busy", job_id))
        return True

    def idle(self):
        self.events.append(("idle", None))
        return True


def metric_worker(jobs, collector, heartbeat=None, *, error=None, factory_error=False):
    def metrics_factory(claimed):
        if factory_error:
            raise RuntimeError("broken metrics")
        return collector

    return SequentialProductionWorker(
        jobs,
        lock_factory=Lock,
        source_factory=lambda snapshot: Source(),
        pipeline_factory=lambda snapshot, cancelled, progress: TimedPipeline(
            progress, error=error
        ),
        result_consumer=lambda snapshot, result: None,
        metrics_factory=metrics_factory,
        heartbeat=heartbeat,
    )


def test_metrics_are_forced_at_start_and_end_and_throttled_between():
    claimed = job()
    jobs = MetricJobs([claimed])
    collector = Collector()

    assert metric_worker(jobs, collector).run_once() is True

    assert jobs.finished == [(claimed.id, JobStatus.SUCCEEDED, None)]
    assert [item[:3] for item in jobs.metrics] == [(0, 0, 0), (20, 2, 0)]
    assert jobs.metrics[-1][3] == {"source_fps": 20.0, "track_count": 0.0}
    assert collector.attached() == (StageTiming("detector", 2, 30.0),)
    assert len(jobs.checkpoints) == 5


def test_due_metrics_are_attached_to_regular_checkpoints():
    claimed = job()
    jobs = MetricJobs([claimed])
    collector = Collector()
    collector.due = lambda: True

    metric_worker(jobs, collector).run_once()

    assert len(jobs.metrics) == len(jobs.checkpoints)


def test_metrics_factory_failure_does_not_fail_the_job():
    claimed = job()
    jobs = MetricJobs([claimed])

    metric_worker(jobs, Collector(), factory_error=True).run_once()

    assert jobs.metrics == []
    assert jobs.finished == [(claimed.id, JobStatus.SUCCEEDED, None)]


def test_heartbeat_marks_busy_then_idle_even_when_job_fails():
    claimed = job()
    jobs = MetricJobs([claimed])
    heartbeat = Heartbeat()

    metric_worker(
        jobs,
        Collector(),
        heartbeat,
        error=AIWorkerError(AIErrorCode.DETECTOR_OUTPUT_INVALID),
    ).run_once()

    assert heartbeat.events == [("busy", claimed.id), ("idle", None)]
    assert jobs.finished[0][1] is JobStatus.FAILED


def test_idle_worker_does_not_report_busy():
    heartbeat = Heartbeat()
    assert metric_worker(MetricJobs([]), Collector(), heartbeat).run_once() is False
    assert heartbeat.events == []


def test_supervisor_passes_worker_id_and_reports_idle_after_child(monkeypatch):
    captured = {}
    child = SimpleNamespace(
        poll=Mock(return_value=0),
        terminate=Mock(),
        kill=Mock(),
        wait=Mock(return_value=0),
    )

    def popen(*args, **kwargs):
        captured.update(kwargs)
        return child

    monkeypatch.setattr("person_search.workers.production_main.subprocess.Popen", popen)
    reporter = SimpleNamespace(worker_id="host:9", safe_beat=Mock(return_value=True))

    class Running:
        def wait(self, seconds):
            return False

        def is_set(self):
            return False

    _supervise_child(Running(), 60, reporter)

    assert captured["env"]["PERSON_SEARCH_WORKER_ID"] == "host:9"
    reporter.safe_beat.assert_called_once_with(WorkerRunState.IDLE, None)
