from __future__ import annotations

import io
import uuid
from collections.abc import Iterable, Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import sqlalchemy as sa

from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    AuditLog,
    OutboxStatus,
    PersonTrack,
    StorageOutboxEvent,
    TrackIndexStatus,
)
from person_search.storage.postgres.models.person_track import ALLOWED_TRACK_TRANSITIONS


def clone(entity: Any) -> Any:
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


class FakeLookup:
    def __init__(self, rows: dict[uuid.UUID, Any]) -> None:
        self.rows = rows

    def get(self, entity_id: uuid.UUID) -> Any:
        return self.rows.get(entity_id)


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


class FakeCaseResults(FakeLookup):
    def exists_for_case_track(self, case_id: uuid.UUID, track_id: uuid.UUID) -> bool:
        return any(
            row.case_id == case_id and row.track_id == track_id for row in self.rows.values()
        )

    def referenced_track_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        referenced = {row.track_id for row in self.rows.values()}
        return {track_id for track_id in track_ids if track_id in referenced}


class FakeAuditLogs:
    def __init__(self, rows: list[AuditLog]) -> None:
        self.rows = rows

    def add(self, entry: AuditLog) -> None:
        self.rows.append(entry)


class FakeUnitOfWork:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.repositories: Any = None

    def __enter__(self) -> FakeUnitOfWork:
        self.tracks = {key: clone(value) for key, value in self.database.tracks.items()}
        self.events = {key: clone(value) for key, value in self.database.events.items()}
        self.audit_logs: list[AuditLog] = []
        self.repositories = SimpleNamespace(
            users=FakeLookup(self.database.users),
            areas=FakeLookup(self.database.areas),
            cameras=FakeLookup(self.database.cameras),
            jobs=FakeLookup(self.database.jobs),
            ai_configs=FakeLookup(self.database.configs),
            cases=FakeLookup(self.database.cases),
            case_results=FakeCaseResults(self.database.case_results),
            tracks=FakeTracks(self.tracks, self.database),
            outbox=FakeOutbox(self.events),
            audit_logs=FakeAuditLogs(self.audit_logs),
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

    def upsert(self, collection_name: str, *, data: dict[str, Any], timeout: int) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.upserts += 1
        self.rows[data["track_id"]] = data

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
        track_id = filter.split('"')[1]
        return [self.rows[track_id]] if track_id in self.rows else []

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
