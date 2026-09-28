from __future__ import annotations

import copy
import io
import uuid
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import sqlalchemy as sa

from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    AuditLog,
    CameraStatus,
    OutboxStatus,
    PersonTrack,
    StorageOutboxEvent,
    TrackIndexStatus,
)
from person_search.storage.postgres.models.person_track import ALLOWED_TRACK_TRANSITIONS


def clone(entity: Any) -> Any:
    if not hasattr(entity, "_sa_instance_state"):
        return copy.copy(entity)
    mapper = sa.inspect(type(entity))
    values = {attribute.key: getattr(entity, attribute.key) for attribute in mapper.column_attrs}
    return type(entity)(**values)


class FakeDatabase:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, Any] = {}
        self.areas: dict[uuid.UUID, Any] = {}
        self.cameras: dict[uuid.UUID, Any] = {}
        self.jobs: dict[uuid.UUID, Any] = {}
        self.configs: dict[uuid.UUID, Any] = {}
        self.cases: dict[uuid.UUID, Any] = {}
        self.case_results: dict[uuid.UUID, Any] = {}
        self.tracks: dict[uuid.UUID, PersonTrack] = {}
        self.events: dict[tuple[uuid.UUID, str], StorageOutboxEvent] = {}
        self.audit_logs: list[AuditLog] = []
        self.commits = 0
        self.commit_failures: dict[int, Exception] = {}
        self.now = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


class FakeLookup:
    def __init__(self, rows: dict[uuid.UUID, Any]) -> None:
        self.rows = rows

    def get(self, entity_id: uuid.UUID) -> Any:
        return self.rows.get(entity_id)


class FakeCameras(FakeLookup):
    def active_ids_in_area(self, area_id: uuid.UUID) -> list[uuid.UUID]:
        return sorted(
            camera.id
            for camera in self.rows.values()
            if camera.area_id == area_id
            and getattr(camera, "status", CameraStatus.ACTIVE) is CameraStatus.ACTIVE
        )


class FakeTracks(FakeLookup):
    def __init__(self, rows: dict[uuid.UUID, PersonTrack], database: FakeDatabase) -> None:
        super().__init__(rows)
        self.database = database

    def add(self, track: PersonTrack) -> None:
        if track.id in self.rows:
            raise DuplicateEntityError("duplicate track")
        self.rows[track.id] = track

    def get_for_update(self, track_id: uuid.UUID) -> PersonTrack | None:
        return self.rows.get(track_id)

    def existing_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        return {track_id for track_id in track_ids if track_id in self.rows}

    def ready_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        return {
            track_id
            for track_id in track_ids
            if track_id in self.rows and self.rows[track_id].index_status is TrackIndexStatus.READY
        }

    def with_location(self, track_ids: Iterable[uuid.UUID]) -> list[tuple[Any, Any, Any]]:
        rows = []
        for track_id in track_ids:
            track = self.rows.get(track_id)
            if track is None:
                continue
            camera = self.database.cameras[track.camera_id]
            rows.append((track, camera, self.database.areas[camera.area_id]))
        return rows

    def page_by_status(
        self,
        status: TrackIndexStatus,
        *,
        limit: int = 100,
        after_id: uuid.UUID | None = None,
    ) -> list[PersonTrack]:
        tracks = sorted(
            (track for track in self.rows.values() if track.index_status is status),
            key=lambda track: track.id,
        )
        if after_id is not None:
            tracks = [track for track in tracks if track.id > after_id]
        return tracks[:limit]

    def count_by_status(self) -> dict[TrackIndexStatus, int]:
        counts: dict[TrackIndexStatus, int] = {}
        for track in self.rows.values():
            counts[track.index_status] = counts.get(track.index_status, 0) + 1
        return counts

    def stale_unready(self, *, updated_before: datetime, limit: int = 100) -> list[PersonTrack]:
        return [
            track
            for track in self.rows.values()
            if track.index_status in (TrackIndexStatus.PENDING, TrackIndexStatus.FAILED)
            and track.updated_at is not None
            and track.updated_at < updated_before
        ][:limit]


class FakeOutbox:
    def __init__(self, rows: dict[tuple[uuid.UUID, str], StorageOutboxEvent]) -> None:
        self.rows = rows

    def add(self, event: StorageOutboxEvent) -> None:
        key = (event.track_id, event.event_type)
        if key in self.rows:
            raise DuplicateEntityError("duplicate outbox event")
        self.rows[key] = event

    def get_for_track(
        self, track_id: uuid.UUID, event_type: str, *, for_update: bool = False
    ) -> StorageOutboxEvent | None:
        return self.rows.get((track_id, event_type))

    def count_by_status(self) -> dict[OutboxStatus, int]:
        counts: dict[OutboxStatus, int] = {}
        for event in self.rows.values():
            counts[event.status] = counts.get(event.status, 0) + 1
        return counts

    def oldest_due_available_at(self, *, now: datetime) -> datetime | None:
        due = [
            event.available_at
            for event in self.rows.values()
            if event.status is OutboxStatus.PENDING and event.available_at <= now
        ]
        return min(due) if due else None

    def claim_due(
        self,
        event_type: str,
        *,
        now: datetime,
        lock_expired_before: datetime,
        limit: int,
    ) -> list[StorageOutboxEvent]:
        due = [
            event
            for (_, kind), event in self.rows.items()
            if kind == event_type
            and (
                (event.status is OutboxStatus.PENDING and event.available_at <= now)
                or (
                    event.status is OutboxStatus.PROCESSING
                    and event.locked_at is not None
                    and event.locked_at < lock_expired_before
                )
            )
        ]
        due.sort(key=lambda event: (event.available_at, event.id))
        for event in due[:limit]:
            event.status = OutboxStatus.PROCESSING
            event.locked_at = now
        return due[:limit]


class FakeCases(FakeLookup):
    def __init__(self, rows: dict[uuid.UUID, Any], database: FakeDatabase) -> None:
        super().__init__(rows)
        self.database = database

    def add(self, case: Any) -> None:
        self.rows[case.id] = case

    def get_for_update(self, case_id: uuid.UUID) -> Any:
        return self.rows.get(case_id)

    def refresh(self, case: Any) -> None:
        pass

    def _with_owner(self, cases: Iterable[Any]) -> list[tuple[Any, Any]]:
        return [(case, self.database.users[case.owner_user_id]) for case in cases]

    def list_page(
        self,
        *,
        owner_user_id: uuid.UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 51,
        status: Any = None,
    ) -> list[tuple[Any, Any]]:
        cases = sorted(
            self.rows.values(), key=lambda case: (case.created_at, case.id), reverse=True
        )
        if owner_user_id is not None:
            cases = [case for case in cases if case.owner_user_id == owner_user_id]
        if created_from is not None:
            cases = [case for case in cases if case.created_at >= created_from]
        if created_to is not None:
            cases = [case for case in cases if case.created_at <= created_to]
        if status is not None:
            cases = [case for case in cases if case.status == status]
        if after is not None:
            cases = [case for case in cases if (case.created_at, case.id) < after]
        return self._with_owner(cases[:limit])

    def recent_with_owner(self, *, limit: int) -> list[tuple[Any, Any]]:
        cases = sorted(
            self.rows.values(), key=lambda case: (case.updated_at, case.id), reverse=True
        )
        return self._with_owner(cases[:limit])

    def count(self) -> int:
        return len(self.rows)

    def count_by_status(self) -> dict[Any, int]:
        counts: dict[Any, int] = {}
        for case in self.rows.values():
            counts[case.status] = counts.get(case.status, 0) + 1
        return counts

    def owners(self) -> list[Any]:
        owner_ids = {case.owner_user_id for case in self.rows.values()}
        return sorted(
            (self.database.users[owner_id] for owner_id in owner_ids),
            key=lambda user: (user.display_name, user.id),
        )


class FakeCaseResults(FakeLookup):
    def add(self, result: Any) -> None:
        self.rows[result.id] = result

    def delete(self, result: Any) -> None:
        self.rows.pop(result.id, None)

    def for_case(self, case_id: uuid.UUID) -> list[Any]:
        return sorted(
            (row for row in self.rows.values() if row.case_id == case_id),
            key=lambda row: (row.saved_at, row.id),
        )

    def count(self) -> int:
        return len(self.rows)

    def count_by_case(self, case_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        wanted = set(case_ids)
        totals: dict[uuid.UUID, int] = {}
        for row in self.rows.values():
            if row.case_id in wanted:
                totals[row.case_id] = totals.get(row.case_id, 0) + 1
        return totals

    def exists_for_case_track(self, case_id: uuid.UUID, track_id: uuid.UUID) -> bool:
        return any(
            row.case_id == case_id and row.track_id == track_id for row in self.rows.values()
        )

    def referenced_track_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        referenced = {row.track_id for row in self.rows.values()}
        return {track_id for track_id in track_ids if track_id in referenced}


class FakeAuditLogs:
    def __init__(self, rows: list[AuditLog], database: FakeDatabase) -> None:
        self.rows = rows
        self.database = database

    def actor_ids(self) -> list[uuid.UUID]:
        return list(
            {row.actor_user_id for row in self.database.audit_logs if row.actor_user_id}
        )

    def add(self, entry: AuditLog) -> None:
        if entry.occurred_at is None:
            entry.occurred_at = self.database.now
        self.rows.append(entry)

    def search(
        self,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        actor_user_id: uuid.UUID | None = None,
        event_types: tuple[str, ...] = (),
        result: Any = None,
        after: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 51,
    ) -> list[AuditLog]:
        rows = sorted(
            self.database.audit_logs,
            key=lambda row: (row.occurred_at, row.id),
            reverse=True,
        )
        if occurred_from is not None:
            rows = [row for row in rows if row.occurred_at >= occurred_from]
        if occurred_to is not None:
            rows = [row for row in rows if row.occurred_at <= occurred_to]
        if actor_user_id is not None:
            rows = [row for row in rows if row.actor_user_id == actor_user_id]
        if event_types:
            rows = [row for row in rows if row.event_type in event_types]
        if result is not None:
            rows = [row for row in rows if row.result is result]
        if after is not None:
            rows = [row for row in rows if (row.occurred_at, row.id) < after]
        return rows[:limit]


class FakeUnitOfWork:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.repositories: Any = None

    def __enter__(self) -> FakeUnitOfWork:
        self.tracks = {key: clone(value) for key, value in self.database.tracks.items()}
        self.events = {key: clone(value) for key, value in self.database.events.items()}
        self.cases = {key: clone(value) for key, value in self.database.cases.items()}
        self.case_results = {
            key: clone(value) for key, value in self.database.case_results.items()
        }
        self.audit_logs: list[AuditLog] = []
        self.repositories = SimpleNamespace(
            users=FakeLookup(self.database.users),
            areas=FakeLookup(self.database.areas),
            cameras=FakeCameras(self.database.cameras),
            jobs=FakeLookup(self.database.jobs),
            ai_configs=FakeLookup(self.database.configs),
            cases=FakeCases(self.cases, self.database),
            case_results=FakeCaseResults(self.case_results),
            tracks=FakeTracks(self.tracks, self.database),
            outbox=FakeOutbox(self.events),
            audit_logs=FakeAuditLogs(self.audit_logs, self.database),
        )
        return self

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.database.commits += 1
        failure = self.database.commit_failures.pop(self.database.commits, None)
        if failure is not None:
            raise failure
        for track_id, track in self.tracks.items():
            previous = self.database.tracks.get(track_id)
            if previous is not None:
                assert track.index_status in ALLOWED_TRACK_TRANSITIONS[previous.index_status]
            if track.index_status is TrackIndexStatus.READY:
                assert track.minio_object_key and track.frame_sha256
                assert track.frame_size_bytes and track.vector_indexed_at is not None
        for key in self.events:
            assert key[0] in self.tracks
        self.database.tracks = self.tracks
        self.database.events = self.events
        self.database.cases = self.cases
        self.database.case_results = self.case_results
        self.database.audit_logs.extend(self.audit_logs)
        self.audit_logs = []

    def __exit__(self, *args: object) -> None:
        pass


class MissingObject(Exception):
    code = "NoSuchKey"


class FakeResponse(io.BytesIO):
    def release_conn(self) -> None:
        pass


class FakeMinioClient:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str, dict[str, str]]] = {}
        self.puts = 0
        self.failures: list[Exception] = []
        self.removed: list[str] = []

    def stat_object(self, bucket: str, key: str) -> SimpleNamespace:
        if key not in self.objects:
            raise MissingObject()
        data, content_type, metadata = self.objects[key]
        return SimpleNamespace(size=len(data), content_type=content_type, metadata=metadata)

    def put_object(
        self,
        bucket: str,
        key: str,
        stream: io.BytesIO,
        length: int,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.puts += 1
        self.objects[key] = (stream.read(length), content_type, metadata)

    def get_object(self, bucket: str, key: str) -> FakeResponse:
        if key not in self.objects:
            raise MissingObject()
        return FakeResponse(self.objects[key][0])

    def list_objects(self, bucket: str, *, prefix: str, recursive: bool) -> Iterator[Any]:
        for key in sorted(self.objects):
            if key.startswith(prefix):
                yield SimpleNamespace(object_name=key)

    def remove_object(self, bucket: str, key: str) -> None:
        self.removed.append(key)
        self.objects.pop(key, None)


class FakeQueryIterator:
    def __init__(self, rows: list[dict[str, Any]], batch_size: int) -> None:
        self.rows = rows
        self.batch_size = batch_size
        self.closed = False

    def next(self) -> list[dict[str, Any]]:
        batch, self.rows = self.rows[: self.batch_size], self.rows[self.batch_size :]
        return batch

    def close(self) -> None:
        self.closed = True


class FakeMilvusClient:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.upserts = 0
        self.failures: list[Exception] = []
        self.query_misses = 0

    def upsert(
        self, collection_name: str, *, data: dict[str, Any] | list[dict[str, Any]], timeout: int
    ) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.upserts += 1
        for row in data if isinstance(data, list) else [data]:
            self.rows[row["track_id"]] = row

    def query(
        self,
        collection_name: str,
        *,
        filter: str,
        output_fields: list[str],
        timeout: int,
        consistency_level: str = "Strong",
    ) -> list[dict[str, Any]]:
        if self.query_misses:
            self.query_misses -= 1
            return []
        # Handles `track_id == "x"` and `track_id in ["x", "y"]`: quoted values are track IDs.
        track_ids = filter.split('"')[1::2]
        return [self.rows[track_id] for track_id in track_ids if track_id in self.rows]

    def query_iterator(
        self,
        collection_name: str,
        *,
        batch_size: int,
        filter: str,
        output_fields: list[str],
        timeout: int,
        consistency_level: str = "Strong",
    ) -> FakeQueryIterator:
        rows = [{"track_id": track_id} for track_id in sorted(self.rows)]
        return FakeQueryIterator(rows, batch_size)

    def delete(self, collection_name: str, *, ids: list[str], timeout: int) -> None:
        for track_id in ids:
            self.rows.pop(track_id, None)
