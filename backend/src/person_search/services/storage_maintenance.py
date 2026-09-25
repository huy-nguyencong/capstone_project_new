from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import islice
from typing import Any, Protocol, TypeVar

from person_search.services.audit import AuditEvent, record_audit
from person_search.services.track_ingestion import (
    TRACK_INGEST_EVENT,
    TrackIngestionService,
)
from person_search.storage.contracts import FRAME_OBJECT_PREFIX
from person_search.storage.minio.frames import FrameInfo, FrameNotFoundError
from person_search.storage.postgres.models import AuditResult, TrackIndexStatus
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

ItemT = TypeVar("ItemT")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _chunks(items: Iterable[ItemT], size: int) -> Iterator[list[ItemT]]:
    iterator = iter(items)
    while chunk := list(islice(iterator, size)):
        yield chunk


def _repositories(work: UnitOfWork) -> Repositories:
    assert work.repositories is not None
    return work.repositories


@dataclass(slots=True)
class OutboxRunSummary:
    claimed: int = 0
    ready: int = 0
    pending: int = 0
    failed: int = 0
    errors: int = 0


class OutboxRetryWorker:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        ingestion: TrackIngestionService,
        *,
        lock_timeout: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._ingestion = ingestion
        self._lock_timeout = lock_timeout
        self._clock = clock

    def run_once(self, *, limit: int = 50) -> OutboxRunSummary:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        now = self._clock()
        with self._unit_of_work_factory() as work:
            events = _repositories(work).outbox.claim_due(
                TRACK_INGEST_EVENT,
                now=now,
                lock_expired_before=now - self._lock_timeout,
                limit=limit,
            )
            track_ids = [event.track_id for event in events]
            work.commit()

        summary = OutboxRunSummary(claimed=len(track_ids))
        for track_id in track_ids:
            try:
                result = self._ingestion.resume(track_id)
            except Exception as error:
                summary.errors += 1
                logger.warning(
                    "outbox retry could not resume track",
                    extra={"track_id": str(track_id), "error_type": type(error).__name__},
                )
                continue
            if result.status is TrackIndexStatus.READY:
                summary.ready += 1
            elif result.status is TrackIndexStatus.PENDING:
                summary.pending += 1
            else:
                summary.failed += 1
        logger.info("outbox retry run finished", extra={"summary": asdict(summary)})
        return summary


class FrameInspector(Protocol):
    def head_frame(self, object_key: str) -> FrameInfo: ...

    def list_frame_keys(self, prefix: str) -> Iterable[str]: ...

    def delete_frame(self, object_key: str) -> None: ...


class VectorInspector(Protocol):
    def get(self, track_id: uuid.UUID) -> dict[str, Any] | None: ...

    def iter_track_ids(self) -> Iterable[uuid.UUID]: ...

    def delete(self, track_id: uuid.UUID) -> None: ...


@dataclass(slots=True)
class ReconciliationReport:
    dry_run: bool
    stale_tracks: list[uuid.UUID] = field(default_factory=list)
    missing_objects: list[uuid.UUID] = field(default_factory=list)
    checksum_mismatches: list[uuid.UUID] = field(default_factory=list)
    missing_vectors: list[uuid.UUID] = field(default_factory=list)
    orphan_objects: list[str] = field(default_factory=list)
    orphan_vectors: list[uuid.UUID] = field(default_factory=list)
    deleted_objects: list[str] = field(default_factory=list)
    deleted_vectors: list[uuid.UUID] = field(default_factory=list)
    truncated: bool = False

    @property
    def clean(self) -> bool:
        return not (
            self.stale_tracks
            or self.missing_objects
            or self.checksum_mismatches
            or self.missing_vectors
            or self.orphan_objects
            or self.orphan_vectors
        )

    def counts(self) -> dict[str, int]:
        return {
            "stale_tracks": len(self.stale_tracks),
            "missing_objects": len(self.missing_objects),
            "checksum_mismatches": len(self.checksum_mismatches),
            "missing_vectors": len(self.missing_vectors),
            "orphan_objects": len(self.orphan_objects),
            "orphan_vectors": len(self.orphan_vectors),
            "deleted_objects": len(self.deleted_objects),
            "deleted_vectors": len(self.deleted_vectors),
        }


def track_id_from_frame_key(object_key: str) -> uuid.UUID | None:
    parts = object_key.split("/")
    if len(parts) < 2:
        return None
    try:
        return uuid.UUID(parts[-2])
    except ValueError:
        return None


class StorageReconciler:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        frames: FrameInspector,
        vectors: VectorInspector,
        *,
        stale_after: timedelta = timedelta(minutes=30),
        batch_size: int = 200,
        max_items: int = 10_000,
        frame_prefix: str = FRAME_OBJECT_PREFIX,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if batch_size < 1 or batch_size > 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self._unit_of_work_factory = unit_of_work_factory
        self._frames = frames
        self._vectors = vectors
        self._stale_after = stale_after
        self._batch_size = batch_size
        self._max_items = max_items
        self._frame_prefix = frame_prefix.rstrip("/")
        self._clock = clock

    def run(
        self, *, delete_orphans: bool = False, actor_user_id: uuid.UUID | None = None
    ) -> ReconciliationReport:
        report = ReconciliationReport(dry_run=not delete_orphans)
        self._find_stale_tracks(report)
        self._check_ready_tracks(report)
        self._find_orphan_objects(report)
        self._find_orphan_vectors(report)
        if delete_orphans:
            self._delete_orphans(report, actor_user_id)
        logger.info(
            "storage reconciliation finished",
            extra={"dry_run": report.dry_run, "counts": report.counts()},
        )
        return report

    def _find_stale_tracks(self, report: ReconciliationReport) -> None:
        with self._unit_of_work_factory() as work:
            tracks = _repositories(work).tracks.stale_unready(
                updated_before=self._clock() - self._stale_after, limit=self._batch_size
            )
            report.stale_tracks.extend(track.id for track in tracks)

    def _check_ready_tracks(self, report: ReconciliationReport) -> None:
        after_id: uuid.UUID | None = None
        inspected = 0
        while inspected < self._max_items:
            with self._unit_of_work_factory() as work:
                tracks = _repositories(work).tracks.page_by_status(
                    TrackIndexStatus.READY, limit=self._batch_size, after_id=after_id
                )
                snapshot = [
                    (track.id, track.minio_object_key, track.frame_sha256) for track in tracks
                ]
            if not snapshot:
                return
            for track_id, object_key, frame_sha256 in snapshot:
                try:
                    info = self._frames.head_frame(object_key or "")
                except FrameNotFoundError:
                    report.missing_objects.append(track_id)
                else:
                    if info.checksum_sha256 != frame_sha256:
                        report.checksum_mismatches.append(track_id)
                if self._vectors.get(track_id) is None:
                    report.missing_vectors.append(track_id)
            inspected += len(snapshot)
            after_id = snapshot[-1][0]
        report.truncated = True

    def _find_orphan_objects(self, report: ReconciliationReport) -> None:
        keys = islice(self._frames.list_frame_keys(self._frame_prefix), self._max_items + 1)
        seen = 0
        for chunk in _chunks(keys, self._batch_size):
            seen += len(chunk)
            if seen > self._max_items:
                report.truncated = True
                chunk = chunk[: len(chunk) - (seen - self._max_items)]
            parsed = {key: track_id_from_frame_key(key) for key in chunk}
            existing = self._existing_track_ids(
                track_id for track_id in parsed.values() if track_id is not None
            )
            report.orphan_objects.extend(
                key for key, track_id in parsed.items() if track_id not in existing
            )

    def _find_orphan_vectors(self, report: ReconciliationReport) -> None:
        track_ids = islice(self._vectors.iter_track_ids(), self._max_items + 1)
        seen = 0
        for chunk in _chunks(track_ids, self._batch_size):
            seen += len(chunk)
            if seen > self._max_items:
                report.truncated = True
                chunk = chunk[: len(chunk) - (seen - self._max_items)]
            existing = self._existing_track_ids(chunk)
            report.orphan_vectors.extend(
                track_id for track_id in chunk if track_id not in existing
            )

    def _existing_track_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        candidates = list(track_ids)
        if not candidates:
            return set()
        with self._unit_of_work_factory() as work:
            repositories = _repositories(work)
            return repositories.tracks.existing_ids(
                candidates
            ) | repositories.case_results.referenced_track_ids(candidates)

    def _delete_orphans(
        self, report: ReconciliationReport, actor_user_id: uuid.UUID | None
    ) -> None:
        object_ids = {key: track_id_from_frame_key(key) for key in report.orphan_objects}
        still_known = self._existing_track_ids(
            [track_id for track_id in object_ids.values() if track_id is not None]
            + report.orphan_vectors
        )
        for key, track_id in object_ids.items():
            if track_id in still_known:
                continue
            self._frames.delete_frame(key)
            report.deleted_objects.append(key)
        for track_id in report.orphan_vectors:
            if track_id in still_known:
                continue
            self._vectors.delete(track_id)
            report.deleted_vectors.append(track_id)
        with self._unit_of_work_factory() as work:
            record_audit(
                _repositories(work),
                event_type=AuditEvent.STORAGE_ORPHANS_DELETED,
                result=AuditResult.SUCCESS,
                target_type="storage",
                actor_user_id=actor_user_id,
                metadata={
                    "deleted_objects": len(report.deleted_objects),
                    "deleted_vectors": len(report.deleted_vectors),
                },
            )
            work.commit()
