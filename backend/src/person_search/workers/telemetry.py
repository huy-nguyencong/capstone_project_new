from __future__ import annotations

import logging
import math
import os
import socket
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import delete

from person_search.storage.postgres.models import WorkerHeartbeat

logger = logging.getLogger(__name__)

JOB_METRIC_KEYS = frozenset(
    {
        "elapsed_ms",
        "source_fps",
        "sampled_fps",
        "detector_ms",
        "tracker_ms",
        "encoder_ms",
        "queue_ms",
        "track_count",
        "error_count",
        "rss_bytes",
        "cpu_percent",
    }
)
STAGE_METRIC_KEYS = {
    "detector": "detector_ms",
    "tracker": "tracker_ms",
    "image_encoder": "encoder_ms",
}
MAX_METRIC_VALUE = 1e15
WORKER_ID_MAX_LENGTH = 128


class WorkerRunState(StrEnum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    BUSY = "BUSY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


def sanitize_metrics(values: Mapping[Any, object]) -> dict[str, float]:
    clean: dict[str, float] = {}
    for key in sorted(JOB_METRIC_KEYS.intersection(values)):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        number = float(value)
        if not math.isfinite(number) or number < 0:
            continue
        clean[key] = round(min(number, MAX_METRIC_VALUE), 3)
    return clean


def default_worker_id() -> str:
    raw = os.getenv("PERSON_SEARCH_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    safe = "".join(char for char in raw if char.isalnum() or char in "._:-")
    return (safe or f"worker:{os.getpid()}")[:WORKER_ID_MAX_LENGTH]


def _rss_bytes() -> int | None:
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError, AttributeError):
        pass
    try:
        import resource
        import sys
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class ResourceSampler:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        cpu_time: Callable[[], float] = time.process_time,
        rss: Callable[[], int | None] = _rss_bytes,
    ) -> None:
        self._clock = clock
        self._cpu_time = cpu_time
        self._rss = rss
        self._last = (clock(), cpu_time())

    def sample(self) -> dict[str, float]:
        now, cpu = self._clock(), self._cpu_time()
        wall = now - self._last[0]
        values: dict[str, float] = {}
        if wall > 0:
            values["cpu_percent"] = max(0.0, (cpu - self._last[1]) / wall * 100)
        self._last = (now, cpu)
        rss = self._rss()
        if rss is not None:
            values["rss_bytes"] = float(rss)
        return values


class JobMetricsCollector:
    def __init__(
        self,
        *,
        queue_ms: float | None = None,
        error_count: int = 0,
        interval_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
        resources: ResourceSampler | None = None,
    ) -> None:
        if isinstance(interval_seconds, bool) or interval_seconds < 0:
            raise ValueError("interval_seconds must be non-negative.")
        self.queue_ms = queue_ms
        self.error_count = max(int(error_count), 0)
        self.interval_seconds = float(interval_seconds)
        self.clock = clock
        self.resources = resources or ResourceSampler(clock=clock)
        self.started = clock()
        self._last_emit: float | None = None
        self._timings: Callable[[], Iterable[Any]] = tuple

    @classmethod
    def for_claimed(cls, job: Any, **kwargs: Any) -> JobMetricsCollector:
        created = getattr(job, "created_at", None)
        started = getattr(job, "started_at", None)
        queue_ms = None
        if isinstance(created, datetime) and isinstance(started, datetime):
            queue_ms = max((started - created).total_seconds() * 1000, 0.0)
        attempts = getattr(job, "attempts", 1) or 1
        return cls(queue_ms=queue_ms, error_count=attempts - 1, **kwargs)

    def attach(self, timings: Callable[[], Iterable[Any]]) -> None:
        self._timings = timings

    def due(self) -> bool:
        if self._last_emit is None:
            return True
        return self.clock() - self._last_emit >= self.interval_seconds

    def snapshot(
        self, source_frames: int, sampled_frames: int, completed_tracks: int
    ) -> dict[str, float]:
        now = self.clock()
        elapsed = max(now - self.started, 0.0)
        values: dict[str, object] = {
            "elapsed_ms": elapsed * 1000,
            "track_count": completed_tracks,
            "error_count": self.error_count,
        }
        if self.queue_ms is not None:
            values["queue_ms"] = self.queue_ms
        if elapsed > 0:
            values["source_fps"] = source_frames / elapsed
            values["sampled_fps"] = sampled_frames / elapsed
        try:
            timings = tuple(self._timings())
        except Exception:
            timings = ()
        for timing in timings:
            key = STAGE_METRIC_KEYS.get(getattr(timing, "stage", None))
            calls = getattr(timing, "calls", 0)
            if key is not None and calls:
                values[key] = getattr(timing, "elapsed_ms", 0.0) / calls
        values.update(self.resources.sample())
        self._last_emit = now
        return sanitize_metrics(values)


def _utc_now() -> datetime:
    return datetime.now(UTC)


_KEEP = object()


class WorkerHeartbeatReporter:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], Any],
        worker_id: str,
        *,
        report_process: bool = True,
        clock: Callable[[], datetime] = _utc_now,
        resources: ResourceSampler | None = None,
        pid: Callable[[], int] = os.getpid,
    ) -> None:
        if not worker_id or len(worker_id) > WORKER_ID_MAX_LENGTH:
            raise ValueError("worker_id must contain 1-128 characters.")
        self.factory = unit_of_work_factory
        self.worker_id = worker_id
        self.report_process = report_process
        self.clock = clock
        self.resources = resources or (ResourceSampler() if report_process else None)
        self.pid = pid

    def beat(
        self, state: WorkerRunState | None = None, job_id: UUID | None | object = _KEEP
    ) -> None:
        with self.factory() as work:
            now = self.clock()
            row = work.session.get(WorkerHeartbeat, self.worker_id, with_for_update=True)
            if row is None:
                row = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    state=(state or WorkerRunState.STARTING).value,
                    started_at=now,
                    state_changed_at=now,
                    heartbeat_at=now,
                )
                work.session.add(row)
            if state is not None and row.state != state.value:
                row.state = state.value
                row.state_changed_at = now
            if job_id is not _KEEP:
                row.current_job_id = job_id
            if self.report_process:
                row.pid = self.pid()
                sample = self.resources.sample() if self.resources is not None else {}
                clean = sanitize_metrics(sample)
                if "rss_bytes" in clean:
                    row.rss_bytes = int(clean["rss_bytes"])
                if "cpu_percent" in clean:
                    row.cpu_percent = clean["cpu_percent"]
            row.heartbeat_at = max(now, row.started_at)
            work.commit()

    def safe_beat(
        self, state: WorkerRunState | None = None, job_id: UUID | None | object = _KEEP
    ) -> bool:
        try:
            self.beat(state, job_id)
            return True
        except Exception as exc:
            logger.warning("Worker heartbeat failed: %s", type(exc).__name__)
            return False

    def busy(self, job_id: UUID) -> bool:
        return self.safe_beat(WorkerRunState.BUSY, job_id)

    def idle(self) -> bool:
        return self.safe_beat(WorkerRunState.IDLE, None)

    def prune(self, older_than: timedelta) -> int:
        if older_than <= timedelta(0):
            raise ValueError("older_than must be positive.")
        with self.factory() as work:
            result = work.session.execute(
                delete(WorkerHeartbeat).where(
                    WorkerHeartbeat.heartbeat_at < self.clock() - older_than,
                    WorkerHeartbeat.worker_id != self.worker_id,
                )
            )
            work.commit()
            return int(result.rowcount or 0)
