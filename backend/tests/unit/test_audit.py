from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from storage_fakes import FakeDatabase, FakeUnitOfWork

from person_search.services.audit import (
    REDACTED,
    AuditAccessDeniedError,
    AuditEvent,
    AuditLogQuery,
    AuditLogService,
    AuditRecorder,
    InvalidAuditQueryError,
    build_audit_log,
    redact_metadata,
)
from person_search.services.track_search import TrackSearchQuery, TrackSearchService
from person_search.storage.postgres.models import AuditResult, UserRole, UserStatus

pytestmark = pytest.mark.unit

START = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


def test_redaction_removes_secrets_vectors_images_and_url_credentials() -> None:
    metadata = {
        "password": "hunter2",
        "new_password_hash": "hash",
        "Authorization": "Bearer abc",
        "session_id": "s-1",
        "api_key": "k",
        "camera": {
            "rtsp_url": "rtsp://cam/stream",
            "note": "reachable via rtsp://admin:pa55@10.0.0.5/stream",
        },
        "embedding": [0.1, 0.2],
        "scores": [0.5] * 256,
        "frame_bytes": b"\xff\xd8",
        "thumbnail": b"raw",
        "deleted_vectors": 3,
        "event_count": 2,
        "message": "line one\nforged: entry",
    }

    redacted = redact_metadata(metadata)

    for key in ("password", "new_password_hash", "Authorization", "session_id", "api_key"):
        assert redacted[key] == REDACTED
    assert redacted["camera"]["rtsp_url"] == REDACTED
    assert "pa55" not in redacted["camera"]["note"]
    assert "rtsp://[REDACTED]@10.0.0.5/stream" in redacted["camera"]["note"]
    assert redacted["embedding"] == REDACTED
    assert redacted["scores"] == REDACTED
    assert redacted["frame_bytes"] == REDACTED
    assert redacted["thumbnail"] == REDACTED
    assert redacted["deleted_vectors"] == 3
    assert redacted["event_count"] == 2
    assert "\n" not in redacted["message"]


def test_redaction_bounds_size_depth_and_normalizes_values() -> None:
    track_id = uuid.uuid4()
    nested: dict[str, object] = {"value": 1}
    for _ in range(10):
        nested = {"child": nested}

    redacted = redact_metadata(
        {
            "long": "x" * 2_000,
            "many": list(range(100)),
            "nested": nested,
            "track_id": track_id,
            "at": START,
            "wide": {f"k{index}": index for index in range(80)},
        }
    )

    assert len(redacted["long"]) <= 501
    assert redacted["many"] == REDACTED
    assert str(REDACTED) in str(redacted["nested"])
    assert redacted["track_id"] == str(track_id)
    assert redacted["at"] == START.isoformat()
    assert redacted["wide"]["_truncated"] is True


def test_audit_entry_requires_catalog_event_and_snapshots_actor() -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), username="admin", role=UserRole.ADMIN)

    entry = build_audit_log(
        event_type=AuditEvent.CAMERA_UPDATED,
        result=AuditResult.SUCCESS,
        target_type="camera",
        actor=actor,  # type: ignore[arg-type]
        metadata={"rtsp_url": "rtsp://user:pw@host/stream"},
    )

    assert entry.actor_user_id == actor.id
    assert entry.event_metadata == {
        "rtsp_url": REDACTED,
        "actor": {"username": "admin", "role": "ADMIN"},
    }
    with pytest.raises(ValueError):
        build_audit_log(
            event_type="custom.event",  # type: ignore[arg-type]
            result=AuditResult.SUCCESS,
            target_type="camera",
        )


def test_standalone_recorder_reports_failure_without_raising() -> None:
    database = FakeDatabase()
    database.commit_failures[1] = ConnectionError("db down")
    recorder = AuditRecorder(lambda: FakeUnitOfWork(database))  # type: ignore[arg-type,return-value]

    stored = recorder.record_standalone(
        event_type=AuditEvent.TECHNICAL_FAILURE,
        result=AuditResult.FAILURE,
        target_type="storage",
    )

    assert stored is False
    assert database.audit_logs == []
    assert recorder.record_standalone(
        event_type=AuditEvent.TECHNICAL_FAILURE,
        result=AuditResult.FAILURE,
        target_type="storage",
    )
    assert len(database.audit_logs) == 1


class AuditWorld:
    def __init__(self) -> None:
        self.database = FakeDatabase()
        self.admin = self._user(UserRole.ADMIN)
        self.operator = self._user(UserRole.OPERATOR)
        self.service = AuditLogService(
            lambda: FakeUnitOfWork(self.database)  # type: ignore[arg-type,return-value]
        )

    def _user(self, role: UserRole, status: UserStatus = UserStatus.ACTIVE) -> uuid.UUID:
        user_id = uuid.uuid4()
        self.database.users[user_id] = SimpleNamespace(
            id=user_id, role=role, status=status, username=role.value.lower()
        )
        return user_id

    def add(
        self,
        event: AuditEvent,
        *,
        minutes: int,
        actor: uuid.UUID | None = None,
        result: AuditResult = AuditResult.SUCCESS,
    ) -> uuid.UUID:
        entry = build_audit_log(
            event_type=event, result=result, target_type="x", actor_user_id=actor
        )
        entry.occurred_at = START + timedelta(minutes=minutes)
        self.database.audit_logs.append(entry)
        return entry.id


def test_audit_query_filters_and_paginates_newest_first() -> None:
    world = AuditWorld()
    ids = [
        world.add(AuditEvent.CASE_CREATED, minutes=minute, actor=world.operator)
        for minute in range(5)
    ]
    world.add(AuditEvent.AUTH_LOGIN, minutes=2, actor=world.admin, result=AuditResult.FAILURE)

    first = world.service.list(
        world.admin, AuditLogQuery(event_types=(AuditEvent.CASE_CREATED,), limit=2)
    )
    second = world.service.list(
        world.admin,
        AuditLogQuery(event_types=(AuditEvent.CASE_CREATED,), limit=2, cursor=first.next_cursor),
    )
    third = world.service.list(
        world.admin,
        AuditLogQuery(event_types=(AuditEvent.CASE_CREATED,), limit=2, cursor=second.next_cursor),
    )

    assert [item.id for page in (first, second, third) for item in page.items] == list(
        reversed(ids)
    )
    assert third.next_cursor is None
    failures = world.service.list(world.admin, AuditLogQuery(result=AuditResult.FAILURE))
    assert [item.event_type for item in failures.items] == ["auth.login"]
    by_actor = world.service.list(world.admin, AuditLogQuery(actor_user_id=world.admin))
    assert len(by_actor.items) == 1
    window = world.service.list(
        world.admin,
        AuditLogQuery(
            occurred_from=START + timedelta(minutes=1), occurred_to=START + timedelta(minutes=3)
        ),
    )
    assert len(window.items) == 4


def test_audit_query_is_admin_only_and_validates_input() -> None:
    world = AuditWorld()
    locked_admin = world._user(UserRole.ADMIN, UserStatus.LOCKED)

    for actor in (world.operator, locked_admin, uuid.uuid4()):
        with pytest.raises(AuditAccessDeniedError):
            world.service.list(actor, AuditLogQuery())
    for query in (
        AuditLogQuery(limit=0),
        AuditLogQuery(limit=101),
        AuditLogQuery(cursor="%%%"),
        AuditLogQuery(occurred_from=datetime(2026, 9, 25)),
        AuditLogQuery(occurred_from=START, occurred_to=START - timedelta(seconds=1)),
    ):
        with pytest.raises(InvalidAuditQueryError):
            world.service.list(world.admin, query)


def test_operator_search_does_not_write_business_audit_events() -> None:
    database = FakeDatabase()
    area_id, operator_id = uuid.uuid4(), uuid.uuid4()
    database.users[operator_id] = SimpleNamespace(
        id=operator_id,
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
        assigned_area_id=area_id,
    )
    searcher = SimpleNamespace(search=lambda vector, filters, top_k: [])
    service = TrackSearchService(
        lambda: FakeUnitOfWork(database),  # type: ignore[arg-type,return-value]
        searcher,  # type: ignore[arg-type]
    )

    service.search(operator_id, TrackSearchQuery([1.0, 0.0], top_k=4))

    assert database.audit_logs == []
