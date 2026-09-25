from __future__ import annotations

import base64
import binascii
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from person_search.storage.postgres.models import (
    AuditLog,
    AuditResult,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
MAX_METADATA_DEPTH = 5
MAX_STRING_LENGTH = 500
MAX_COLLECTION_ITEMS = 50
MAX_AUDIT_PAGE = 100


class AuditEvent(StrEnum):
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_SESSION_EXPIRED = "auth.session_expired"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_STATUS_CHANGED = "user.status_changed"
    USER_ROLE_CHANGED = "user.role_changed"
    OPERATOR_AREA_ASSIGNED = "operator.area_assigned"
    CAMERA_CREATED = "camera.created"
    CAMERA_UPDATED = "camera.updated"
    CAMERA_DEACTIVATED = "camera.deactivated"
    CAMERA_CONNECTION_TESTED = "camera.connection_tested"
    AI_STATE_CHANGED = "ai.state_changed"
    AI_CONFIG_REQUESTED = "ai.config_requested"
    AI_CONFIG_APPLIED = "ai.config_applied"
    AI_CONFIG_FAILED = "ai.config_failed"
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_RESULT_ADDED = "case.result_added"
    CASE_RESULT_REMOVED = "case.result_removed"
    STORAGE_TRACK_FAILED = "storage.track_failed"
    STORAGE_TRACK_REQUEUED = "storage.track_requeued"
    STORAGE_ORPHANS_DELETED = "storage.orphans_deleted"
    TECHNICAL_FAILURE = "system.technical_failure"


_SENSITIVE_KEY = re.compile(
    r"^(?:.*[_.-])?(password|password_hash|passwd|secret|token|api_key|apikey|access_key|"
    r"secret_key|private_key|credential|credentials|authorization|cookie|session_id|"
    r"embedding|vector|frame_bytes|image_bytes|raw_image|rtsp_url)$",
    re.IGNORECASE,
)
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _redact_string(value: str) -> str:
    cleaned = _URL_CREDENTIALS.sub(lambda match: f"{match['scheme']}{REDACTED}@", value)
    cleaned = _CONTROL_CHARACTERS.sub(" ", cleaned)
    if len(cleaned) > MAX_STRING_LENGTH:
        cleaned = cleaned[:MAX_STRING_LENGTH] + "…"
    return cleaned


def _is_numeric_vector(value: list[Any] | tuple[Any, ...]) -> bool:
    return len(value) > 16 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    )


def redact_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_METADATA_DEPTH:
        return REDACTED
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_COLLECTION_ITEMS:
                redacted["_truncated"] = True
                break
            name = _redact_string(str(key))
            redacted[name] = (
                REDACTED if _SENSITIVE_KEY.match(name) else redact_metadata(item, depth=depth + 1)
            )
        return redacted
    if isinstance(value, (list, tuple)):
        if _is_numeric_vector(value):
            return REDACTED
        items = [redact_metadata(item, depth=depth + 1) for item in value[:MAX_COLLECTION_ITEMS]]
        if len(value) > MAX_COLLECTION_ITEMS:
            items.append("…")
        return items
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return _redact_string(str(value))


def _actor_snapshot(actor: User | None) -> dict[str, str] | None:
    if actor is None:
        return None
    return {"username": actor.username, "role": actor.role.value}


def build_audit_log(
    *,
    event_type: AuditEvent,
    result: AuditResult,
    target_type: str,
    target_id: uuid.UUID | None = None,
    actor: User | None = None,
    actor_user_id: uuid.UUID | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AuditLog:
    if not isinstance(event_type, AuditEvent):
        raise ValueError("event_type must come from the AuditEvent catalog")
    body = dict(redact_metadata(dict(metadata or {})))
    snapshot = _actor_snapshot(actor)
    if snapshot is not None:
        body["actor"] = snapshot
    return AuditLog(
        id=uuid.uuid4(),
        actor_user_id=actor.id if actor is not None else actor_user_id,
        event_type=event_type.value,
        target_type=target_type,
        target_id=target_id,
        result=result,
        event_metadata=body,
    )


def record_audit(repositories: Repositories, **kwargs: Any) -> AuditLog:
    entry = build_audit_log(**kwargs)
    repositories.audit_logs.add(entry)
    return entry


class AuditRecorder:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def record_standalone(self, **kwargs: Any) -> bool:
        try:
            with self._unit_of_work_factory() as work:
                assert work.repositories is not None
                record_audit(work.repositories, **kwargs)
                work.commit()
        except Exception as error:
            logger.error(
                "audit event could not be stored",
                extra={
                    "event_type": str(kwargs.get("event_type")),
                    "error_type": type(error).__name__,
                },
            )
            return False
        return True


class AuditAccessDeniedError(PermissionError):
    pass


class InvalidAuditQueryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AuditLogQuery:
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    actor_user_id: uuid.UUID | None = None
    event_types: tuple[AuditEvent, ...] = ()
    result: AuditResult | None = None
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class AuditLogView:
    id: uuid.UUID
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    event_type: str
    target_type: str
    target_id: uuid.UUID | None
    result: AuditResult
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuditLogPage:
    items: list[AuditLogView]
    next_cursor: str | None


def encode_audit_cursor(occurred_at: datetime, entry_id: uuid.UUID) -> str:
    raw = f"{occurred_at.isoformat()}|{entry_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_audit_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        occurred_at, entry_id = base64.urlsafe_b64decode(padded).decode().split("|")
        parsed = datetime.fromisoformat(occurred_at)
        if parsed.tzinfo is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        return parsed, uuid.UUID(entry_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidAuditQueryError("Audit cursor is invalid.") from error


class AuditLogService:
    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def list(self, actor_user_id: uuid.UUID, query: AuditLogQuery) -> AuditLogPage:
        if query.limit < 1 or query.limit > MAX_AUDIT_PAGE:
            raise InvalidAuditQueryError(f"limit must be between 1 and {MAX_AUDIT_PAGE}.")
        for value in (query.occurred_from, query.occurred_to):
            if value is not None and value.tzinfo is None:
                raise InvalidAuditQueryError("Time filters must be timezone-aware.")
        if (
            query.occurred_from is not None
            and query.occurred_to is not None
            and query.occurred_from > query.occurred_to
        ):
            raise InvalidAuditQueryError("occurred_from must not be after occurred_to.")
        after = decode_audit_cursor(query.cursor) if query.cursor else None
        with self._unit_of_work_factory() as work:
            repositories = work.repositories
            assert repositories is not None
            actor = repositories.users.get(actor_user_id)
            if actor is None or actor.status is not UserStatus.ACTIVE or actor.role is not (
                UserRole.ADMIN
            ):
                raise AuditAccessDeniedError("Only an active Admin can read audit logs.")
            rows = repositories.audit_logs.search(
                occurred_from=query.occurred_from,
                occurred_to=query.occurred_to,
                actor_user_id=query.actor_user_id,
                event_types=tuple(event.value for event in query.event_types),
                result=query.result,
                after=after,
                limit=query.limit + 1,
            )
        has_more = len(rows) > query.limit
        rows = rows[: query.limit]
        items = [
            AuditLogView(
                id=row.id,
                occurred_at=row.occurred_at,
                actor_user_id=row.actor_user_id,
                event_type=row.event_type,
                target_type=row.target_type,
                target_id=row.target_id,
                result=row.result,
                metadata=dict(row.event_metadata),
            )
            for row in rows
        ]
        next_cursor = (
            encode_audit_cursor(rows[-1].occurred_at, rows[-1].id) if has_more and rows else None
        )
        return AuditLogPage(items, next_cursor)
