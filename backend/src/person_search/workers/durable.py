"""Durable sequential execution loop for production AI jobs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import text

from person_search.observability import log_context
from person_search.storage.postgres.models import JobSourceType, JobStatus
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipelineResult
from person_search.workers.telemetry import JobMetricsCollector, WorkerHeartbeatReporter

WORKER_LOCK = 734202
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JobExecutionSnapshot:
    job_id: UUID
    lease_token: UUID
    camera_id: UUID
    ai_config_version_id: UUID
    source_type: JobSourceType
    source_ref: str
    sampling_interval: int
    timeline_origin_utc: datetime
    attempts: int
    published_tracks: int = 0

    @classmethod
    def from_claimed(cls, job) -> JobExecutionSnapshot:
        if job.source_type is not JobSourceType.FILE or not job.source_ref:
            raise ValueError("Production file worker requires a staged FILE source.")
        if job.lease_token is None:
            raise ValueError("Claimed job must contain a lease token.")
        if job.sampling_interval < 1:
            raise ValueError("Claimed job sampling interval must be positive.")
        return cls(
            job.id,
            job.lease_token,
            job.camera_id,
            job.ai_config_version_id,
            job.source_type,
            job.source_ref,
            job.sampling_interval,
            job.timeline_origin_utc,
            job.attempts,
            getattr(job, "published_tracks", 0),
        )


class WorkerLock(Protocol):
    def __enter__(self) -> bool: ...

    def __exit__(self, exc_type, exc, traceback) -> None: ...


class PostgresWorkerLock(AbstractContextManager):
    """Hold one session-level advisory lock for the entire claimed job."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.connection = None
        self.acquired = False

    def __enter__(self) -> bool:
        self.connection = self.engine.connect()
        self.acquired = bool(
            self.connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}
            )
        )
        self.connection.commit()
        return self.acquired

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.connection is None:
            return
        try:
            if self.acquired:
                self.connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK}
                )
                self.connection.commit()
        finally:
            self.connection.close()


class LeaseLost(RuntimeError):
    pass


class GracefulStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WorkerRetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 5.0
    max_delay_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds <= 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("retry delays must be positive and ordered")

    def delay_after(self, attempts: int) -> timedelta:
        seconds = self.base_delay_seconds * 2 ** max(attempts - 1, 0)
        return timedelta(seconds=min(seconds, self.max_delay_seconds))


class _JobControl:
    def __init__(
        self,
        jobs,
        snapshot: JobExecutionSnapshot,
        stop: Callable[[], bool],
        metrics: JobMetricsCollector | None = None,
    ) -> None:
        self.jobs = jobs
        self.snapshot = snapshot
        self.stop = stop
        self.metrics = metrics
        self.source_frames = 0
        self.sampled_frames = 0
        self.completed_tracks = 0

    def attach(self, pipeline) -> None:
        timings = getattr(pipeline, "stage_timings", None)
        if self.metrics is not None and callable(timings):
            self.metrics.attach(timings)

    def progress(
        self,
        source_frames: int,
        sampled_frames: int,
        completed_tracks: int,
        *,
        force_metrics: bool = False,
    ) -> None:
        self.source_frames = source_frames
        self.sampled_frames = sampled_frames
        self.completed_tracks = completed_tracks
        self.checkpoint(force_metrics=force_metrics)

    def checkpoint(self, *, force_metrics: bool = False) -> None:
        if self.stop():
            raise GracefulStop
        extra = {}
        if self.metrics is not None and (force_metrics or self.metrics.due()):
            extra["metrics"] = self.metrics.snapshot(
                self.source_frames, self.sampled_frames, self.completed_tracks
            )
        if not self.jobs.checkpoint(
            self.snapshot.job_id,
            self.snapshot.lease_token,
            self.source_frames,
            self.sampled_frames,
            self.completed_tracks,
            0,
            **extra,
        ):
            raise LeaseLost

    def cancelled(self) -> bool:
        self.checkpoint()
        return False


class SequentialProductionWorker:
    """Claim and execute at most one job at a time under the global worker lock."""

    def __init__(
        self,
        jobs,
        *,
        lock_factory: Callable[[], WorkerLock],
        source_factory,
        pipeline_factory,
        result_consumer: Callable[[JobExecutionSnapshot, ProductionPipelineResult], None],
        stop: Callable[[], bool] = lambda: False,
        max_attempts: int = 3,
        retry_policy: WorkerRetryPolicy | None = None,
        metrics_factory: Callable[[object], JobMetricsCollector] | None = None,
        heartbeat: WorkerHeartbeatReporter | None = None,
    ) -> None:
        self.jobs = jobs
        self.lock_factory = lock_factory
        self.source_factory = source_factory
        self.pipeline_factory = pipeline_factory
        self.result_consumer = result_consumer
        self.stop = stop
        self.retry_policy = retry_policy or WorkerRetryPolicy(max_attempts=max_attempts)
        self.max_attempts = self.retry_policy.max_attempts
        self.metrics_factory = metrics_factory
        self.heartbeat = heartbeat

    def run_once(self) -> bool:
        with self.lock_factory() as acquired:
            if not acquired:
                return False
            if self.stop():
                return False
            self.jobs.cleanup()
            job = self.jobs.claim()
            if job is None:
                return False
            if self.heartbeat is not None:
                self.heartbeat.busy(job.id)
            try:
                self._execute(job)
            finally:
                if self.heartbeat is not None:
                    self.heartbeat.idle()
            return True

    def run_until_idle(self, *, max_jobs: int | None = None) -> int:
        completed = 0
        while max_jobs is None or completed < max_jobs:
            if self.stop() or not self.run_once():
                break
            completed += 1
        return completed

    def _metrics_for(self, job) -> JobMetricsCollector | None:
        if self.metrics_factory is None:
            return None
        try:
            return self.metrics_factory(job)
        except Exception:
            return None

    def _execute(self, job) -> None:
        with log_context(
            job_id=getattr(job, "id", None),
            camera_id=getattr(job, "camera_id", None),
            ai_config_version_id=getattr(job, "ai_config_version_id", None),
        ):
            logger.info("job claimed", extra={"attempt": getattr(job, "attempts", None)})
            self._execute_job(job)

    def _execute_job(self, job) -> None:
        result = None
        snapshot = None
        try:
            snapshot = JobExecutionSnapshot.from_claimed(job)
            if snapshot.attempts > self.max_attempts:
                self.jobs.finish(
                    snapshot.job_id,
                    snapshot.lease_token,
                    JobStatus.FAILED,
                    "worker_retries_exhausted",
                )
                return
            control = _JobControl(
                self.jobs, snapshot, self.stop, self._metrics_for(job)
            )
            control.checkpoint(force_metrics=True)
            source = self.source_factory(snapshot)
            pipeline = self.pipeline_factory(snapshot, control.cancelled, control.progress)
            control.attach(pipeline)
            with source:
                result = pipeline.run(source)
            control.progress(
                result.source_frames,
                result.sampled_frames,
                len(result.encoded_tracks),
                force_metrics=True,
            )
            self.result_consumer(snapshot, result)
            control.checkpoint()
            self.jobs.finish(
                snapshot.job_id, snapshot.lease_token, JobStatus.SUCCEEDED
            )
            logger.info(
                "job succeeded",
                extra={
                    "source_frames": result.source_frames,
                    "sampled_frames": result.sampled_frames,
                    "completed_tracks": len(result.encoded_tracks),
                },
            )
        except GracefulStop:
            logger.info("job left running for lease recovery after graceful stop")
            # Leave RUNNING + lease for deterministic recovery by a later worker.
            return
        except LeaseLost:
            logger.warning("job lease lost or cancellation requested")
            self.jobs.finish(job.id, job.lease_token, JobStatus.CANCELLED)
        except AIWorkerError as exc:
            logger.warning(
                "job stage failed",
                exc_info=exc.code is not AIErrorCode.CANCELLED,
                extra={
                    "error_code": exc.code.value,
                    "stage": exc.stage.value,
                    "retryable": exc.retryable,
                },
            )
            if exc.code is AIErrorCode.CANCELLED:
                self.jobs.finish(job.id, job.lease_token, JobStatus.CANCELLED)
            elif exc.retryable and snapshot is not None and snapshot.attempts < self.max_attempts:
                self.jobs.defer_retry(
                    job.id,
                    job.lease_token,
                    exc.code.value,
                    self.retry_policy.delay_after(snapshot.attempts),
                )
            else:
                error_code = (
                    "worker_retries_exhausted"
                    if exc.retryable and snapshot is not None
                    else exc.code.value
                )
                self.jobs.finish(job.id, job.lease_token, JobStatus.FAILED, error_code)
        except Exception:
            logger.exception(
                "job execution failed", extra={"error_code": "worker_execution_failed"}
            )
            self.jobs.finish(job.id, job.lease_token, JobStatus.FAILED, "worker_execution_failed")
        finally:
            if result is not None:
                images = {
                    id(item.track.representative.frame.image): item.track.representative.frame.image
                    for item in result.encoded_tracks
                }
                for image in images.values():
                    image.close()


def staged_file_source_factory(staging, *, max_bytes: int):
    """Create the default FILE source factory without exposing staging paths in logs."""

    from person_search.workers.sources import FileFrameSource

    def create(snapshot: JobExecutionSnapshot):
        path: Path = staging.path(snapshot.source_ref)
        return FileFrameSource(max_bytes=max_bytes).open(path, camera_id=snapshot.camera_id)

    return create
