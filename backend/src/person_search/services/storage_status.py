from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from person_search.storage.postgres.models import (
    OutboxStatus,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork


class StorageComponent(StrEnum):
    POSTGRES = "postgres"
    MINIO = "minio"
    MILVUS = "milvus"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ComponentErrors:
    count: int = 0
    last_error_type: str | None = None
    last_error_at: datetime | None = None


@dataclass(slots=True)
class IngestionTimings:
    runs: int = 0
    ready: int = 0
    pending: int = 0
    failed: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0

    @property
    def average_ms(self) -> float:
        return self.total_ms / self.runs if self.runs else 0.0


class StorageMetrics:
    def __init__(self, clock: Callable[[], datetime] = _utc_now) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._errors = {component: ComponentErrors() for component in StorageComponent}
        self._ingestion = IngestionTimings()

    def record_error(self, component: StorageComponent, error: BaseException) -> None:
        with self._lock:
            stats = self._errors[component]
            stats.count += 1
            stats.last_error_type = type(error).__name__
            stats.last_error_at = self._clock()

    def record_ingestion(self, status: TrackIndexStatus, duration_ms: float) -> None:
        with self._lock:
            timings = self._ingestion
            timings.runs += 1
            timings.total_ms += duration_ms
            timings.max_ms = max(timings.max_ms, duration_ms)
            if status is TrackIndexStatus.READY:
                timings.ready += 1
            elif status is TrackIndexStatus.PENDING:
                timings.pending += 1
            else:
                timings.failed += 1

    def errors(self) -> dict[StorageComponent, ComponentErrors]:
        with self._lock:
            return {
                component: ComponentErrors(
                    stats.count, stats.last_error_type, stats.last_error_at
                )
                for component, stats in self._errors.items()
            }

    def ingestion(self) -> IngestionTimings:
        with self._lock:
            current = self._ingestion
            return IngestionTimings(
                current.runs,
                current.ready,
                current.pending,
                current.failed,
                current.total_ms,
                current.max_ms,
            )


class HealthChecker(Protocol):
    def check(self) -> Any: ...


class StatusAccessDeniedError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class StorageStatus:
    generated_at: datetime
    tracks_by_status: dict[str, int]
    outbox_by_status: dict[str, int]
    oldest_due_outbox_age_seconds: float | None
    component_errors: dict[str, ComponentErrors]
    component_health: dict[str, str]
    ingestion: IngestionTimings
    warnings: list[str] = field(default_factory=list)


class StorageStatusService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        metrics: StorageMetrics,
        *,
        health: HealthChecker | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._metrics = metrics
        self._health = health
        self._clock = clock

    def snapshot(self, actor_user_id: uuid.UUID) -> StorageStatus:
        now = self._clock()
        component_health: dict[str, str] = {}
        warnings: list[str] = []
        if self._health is not None:
            report = self._health.check()
            component_health = {
                name: str(values.get("status", "unknown"))
                for name, values in report.components.items()
            }
        with self._unit_of_work_factory() as work:
            repositories = work.repositories
            assert repositories is not None
            actor = repositories.users.get(actor_user_id)
            if actor is None or actor.status is not UserStatus.ACTIVE or actor.role is not (
                UserRole.ADMIN
            ):
                raise StatusAccessDeniedError("Only an active Admin can read storage status.")
            tracks = repositories.tracks.count_by_status()
            outbox = repositories.outbox.count_by_status()
            oldest_due = repositories.outbox.oldest_due_available_at(now=now)

        tracks_by_status = {status.value: tracks.get(status, 0) for status in TrackIndexStatus}
        outbox_by_status = {status.value: outbox.get(status, 0) for status in OutboxStatus}
        oldest_age = (now - oldest_due).total_seconds() if oldest_due is not None else None
        if outbox_by_status[OutboxStatus.DEAD.value]:
            warnings.append("dead_outbox_events")
        if tracks_by_status[TrackIndexStatus.FAILED.value]:
            warnings.append("failed_tracks")
        for name, status in component_health.items():
            if status != "ok":
                warnings.append(f"{name}_unhealthy")
        return StorageStatus(
            generated_at=now,
            tracks_by_status=tracks_by_status,
            outbox_by_status=outbox_by_status,
            oldest_due_outbox_age_seconds=oldest_age,
            component_errors={
                component.value: stats for component, stats in self._metrics.errors().items()
            },
            component_health=component_health,
            ingestion=self._metrics.ingestion(),
            warnings=warnings,
        )
