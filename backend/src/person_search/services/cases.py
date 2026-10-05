from __future__ import annotations

import base64
import binascii
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from person_search.services.audit import AuditEvent, AuditRecorder, record_audit
from person_search.services.case_policy import (
    CaseOwnerNotAllowedError,
    owner_id_from_authenticated_actor,
)
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import (
    AuditResult,
    CameraStatus,
    Case,
    CaseResult,
    CaseStatus,
    PersonTrack,
    TrackIndexStatus,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

TITLE_MAX_LENGTH = 200
NOTE_MAX_LENGTH = 5000
MAX_CASE_PAGE = 100
MAX_RECENT_CASES = 50


class CaseAccessDeniedError(PermissionError):
    pass


class CaseNotFoundError(LookupError):
    pass


class InvalidCaseRequestError(ValueError):
    pass


class CaseClosedError(RuntimeError):
    """A completed Case is read-only until its owner reopens it."""


class TrackNotSavableError(PermissionError):
    pass


class _Unset:
    pass


UNSET: Any = _Unset()


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CaseSummary:
    id: uuid.UUID
    title: str
    note: str | None
    owner_user_id: uuid.UUID
    owner_display_name: str
    owner_status: UserStatus
    result_count: int
    created_at: datetime
    updated_at: datetime
    version: int
    status: CaseStatus = CaseStatus.OPEN
    closed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CaseResultView:
    id: uuid.UUID
    case_id: uuid.UUID
    track_id: uuid.UUID
    camera_name: str
    area_name: str
    appeared_at: datetime
    saved_at: datetime
    bbox: BoundingBoxPixels | None = None


@dataclass(frozen=True, slots=True)
class CaseDetail:
    case: CaseSummary
    results: list[CaseResultView]


@dataclass(frozen=True, slots=True)
class CaseListQuery:
    owner_user_id: uuid.UUID | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    limit: int = 20
    cursor: str | None = None
    status: CaseStatus | None = None


@dataclass(frozen=True, slots=True)
class CasePage:
    items: list[CaseSummary]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CaseOwnerView:
    id: uuid.UUID
    display_name: str
    status: UserStatus


@dataclass(frozen=True, slots=True)
class ViewerDashboard:
    total_cases: int
    total_case_results: int
    recent_cases: list[CaseSummary]
    open_cases: int = 0
    closed_cases: int = 0


def _clean_title(title: str) -> str:
    if not isinstance(title, str) or not title.strip():
        raise InvalidCaseRequestError("Case title must not be blank.")
    cleaned = title.strip()
    if len(cleaned) > TITLE_MAX_LENGTH:
        raise InvalidCaseRequestError(f"Case title must be at most {TITLE_MAX_LENGTH} characters.")
    return cleaned


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    if not isinstance(note, str):
        raise InvalidCaseRequestError("Case note must be text.")
    cleaned = note.strip()
    if len(cleaned) > NOTE_MAX_LENGTH:
        raise InvalidCaseRequestError(f"Case note must be at most {NOTE_MAX_LENGTH} characters.")
    return cleaned or None


def _encode_cursor(created_at: datetime, case_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{case_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        created_at, case_id = base64.urlsafe_b64decode(padded).decode().split("|")
        parsed = datetime.fromisoformat(created_at)
        if parsed.tzinfo is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        return parsed, uuid.UUID(case_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidCaseRequestError("Case cursor is invalid.") from error


def _summary(case: Case, owner: User, result_count: int) -> CaseSummary:
    return CaseSummary(
        id=case.id,
        title=case.title,
        note=case.note,
        owner_user_id=case.owner_user_id,
        owner_display_name=owner.display_name,
        owner_status=owner.status,
        result_count=result_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
        version=case.version,
        status=case.status,
        closed_at=case.closed_at,
    )


def _bbox(track: PersonTrack | None) -> BoundingBoxPixels | None:
    if track is None:
        return None
    try:
        return BoundingBoxPixels(
            track.bbox_x,
            track.bbox_y,
            track.bbox_width,
            track.bbox_height,
            track.frame_width,
            track.frame_height,
        )
    except (TypeError, ValueError):
        return None


def _result_view(result: CaseResult, track: PersonTrack | None = None) -> CaseResultView:
    return CaseResultView(
        id=result.id,
        case_id=result.case_id,
        track_id=result.track_id,
        camera_name=result.camera_name_snapshot,
        area_name=result.area_name_snapshot,
        appeared_at=result.appeared_at_snapshot,
        saved_at=result.saved_at,
        bbox=_bbox(track),
    )


class CaseService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        *,
        audit: AuditRecorder | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._audit = audit
        self._clock = clock

    def create_case(
        self,
        actor_user_id: uuid.UUID,
        *,
        title: str,
        note: str | None = None,
        track_id: uuid.UUID | None = None,
    ) -> CaseDetail:
        clean_title = _clean_title(title)
        clean_note = _clean_note(note)
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._operator(repositories, actor_user_id, AuditEvent.CASE_CREATED, None)
            now = self._clock()
            case = Case(
                id=uuid.uuid4(),
                owner_user_id=owner_id_from_authenticated_actor(actor.id, actor.role),
                title=clean_title,
                note=clean_note,
                created_at=now,
                updated_at=now,
                version=1,
                status=CaseStatus.OPEN,
                closed_at=None,
            )
            repositories.cases.add(case)
            work.flush()
            results: list[tuple[CaseResult, PersonTrack]] = []
            if track_id is not None:
                results.append(self._save_track(repositories, actor, case, track_id, now))
            record_audit(
                repositories,
                event_type=AuditEvent.CASE_CREATED,
                result=AuditResult.SUCCESS,
                target_type="case",
                target_id=case.id,
                actor=actor,
                metadata={"has_note": clean_note is not None, "initial_results": len(results)},
            )
            work.commit()
            return CaseDetail(
                _summary(case, actor, len(results)),
                [_result_view(row, track) for row, track in results],
            )

    def update_case(
        self,
        actor_user_id: uuid.UUID,
        case_id: uuid.UUID,
        *,
        title: Any = UNSET,
        note: Any = UNSET,
        status: Any = UNSET,
        expected_updated_at: datetime | None = None,
        expected_version: int | None = None,
    ) -> CaseSummary:
        changes: dict[str, Any] = {}
        if title is not UNSET:
            changes["title"] = _clean_title(title)
        if note is not UNSET:
            changes["note"] = _clean_note(note)
        if status is not UNSET and not isinstance(status, CaseStatus):
            raise InvalidCaseRequestError("status must be OPEN or CLOSED.")
        if not changes and status is UNSET:
            raise InvalidCaseRequestError("Nothing to update.")
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._operator(repositories, actor_user_id, AuditEvent.CASE_UPDATED, case_id)
            case = self._owned_case(repositories, actor, case_id, AuditEvent.CASE_UPDATED)
            if expected_updated_at is not None and case.updated_at != expected_updated_at:
                raise ConcurrentUpdateError("Case was changed by another transaction.")
            if expected_version is not None and case.version != expected_version:
                raise ConcurrentUpdateError("Case was changed by another request.")
            reopening = status is CaseStatus.OPEN
            if case.status is CaseStatus.CLOSED and changes and not reopening:
                raise CaseClosedError("Case is completed; reopen it before editing.")
            changed = sorted(key for key, value in changes.items() if getattr(case, key) != value)
            for key, value in changes.items():
                setattr(case, key, value)
            now = self._clock()
            status_event = None
            if status is not UNSET and status is not case.status:
                case.status = status
                case.closed_at = now if status is CaseStatus.CLOSED else None
                status_event = (
                    AuditEvent.CASE_CLOSED
                    if status is CaseStatus.CLOSED
                    else AuditEvent.CASE_REOPENED
                )
            case.version += 1
            case.updated_at = now
            if changes:
                record_audit(
                    repositories,
                    event_type=AuditEvent.CASE_UPDATED,
                    result=AuditResult.SUCCESS,
                    target_type="case",
                    target_id=case.id,
                    actor=actor,
                    metadata={"changed_fields": changed},
                )
            if status_event is not None:
                record_audit(
                    repositories,
                    event_type=status_event,
                    result=AuditResult.SUCCESS,
                    target_type="case",
                    target_id=case.id,
                    actor=actor,
                    metadata={"status": case.status.value},
                )
            work.flush()
            repositories.cases.refresh(case)
            result_count = repositories.case_results.count_by_case([case.id]).get(case.id, 0)
            work.commit()
            return _summary(case, actor, result_count)

    def add_result(
        self, actor_user_id: uuid.UUID, case_id: uuid.UUID, track_id: uuid.UUID
    ) -> CaseResultView:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._operator(
                repositories, actor_user_id, AuditEvent.CASE_RESULT_ADDED, case_id
            )
            case = self._owned_case(repositories, actor, case_id, AuditEvent.CASE_RESULT_ADDED)
            if case.status is CaseStatus.CLOSED:
                raise CaseClosedError("Case is completed; reopen it before adding results.")
            now = self._clock()
            result, track = self._save_track(repositories, actor, case, track_id, now)
            case.updated_at = now
            record_audit(
                repositories,
                event_type=AuditEvent.CASE_RESULT_ADDED,
                result=AuditResult.SUCCESS,
                target_type="case",
                target_id=case.id,
                actor=actor,
                metadata={"case_result_id": result.id, "track_id": track_id},
            )
            work.commit()
            return _result_view(result, track)

    def remove_result(
        self, actor_user_id: uuid.UUID, case_id: uuid.UUID, case_result_id: uuid.UUID
    ) -> None:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._operator(
                repositories, actor_user_id, AuditEvent.CASE_RESULT_REMOVED, case_id
            )
            case = self._owned_case(repositories, actor, case_id, AuditEvent.CASE_RESULT_REMOVED)
            if case.status is CaseStatus.CLOSED:
                raise CaseClosedError("Case is completed; reopen it before removing results.")
            result = repositories.case_results.get(case_result_id)
            if result is None or result.case_id != case.id:
                raise CaseNotFoundError("Case result was not found.")
            track_id = result.track_id
            repositories.case_results.delete(result)
            case.updated_at = self._clock()
            record_audit(
                repositories,
                event_type=AuditEvent.CASE_RESULT_REMOVED,
                result=AuditResult.SUCCESS,
                target_type="case",
                target_id=case.id,
                actor=actor,
                metadata={"case_result_id": case_result_id, "track_id": track_id},
            )
            work.commit()

    def list_cases(self, actor_user_id: uuid.UUID, query: CaseListQuery) -> CasePage:
        if query.limit < 1 or query.limit > MAX_CASE_PAGE:
            raise InvalidCaseRequestError(f"limit must be between 1 and {MAX_CASE_PAGE}.")
        for value in (query.created_from, query.created_to):
            if value is not None and value.tzinfo is None:
                raise InvalidCaseRequestError("Time filters must be timezone-aware.")
        after = _decode_cursor(query.cursor) if query.cursor else None
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._reader(repositories, actor_user_id)
            owner_filter = actor.id if actor.role is UserRole.OPERATOR else query.owner_user_id
            rows = repositories.cases.list_page(
                owner_user_id=owner_filter,
                created_from=query.created_from,
                created_to=query.created_to,
                after=after,
                limit=query.limit + 1,
                status=query.status,
            )
            has_more = len(rows) > query.limit
            rows = rows[: query.limit]
            counts = repositories.case_results.count_by_case(case.id for case, _ in rows)
        items = [_summary(case, owner, counts.get(case.id, 0)) for case, owner in rows]
        next_cursor = (
            _encode_cursor(rows[-1][0].created_at, rows[-1][0].id) if has_more and rows else None
        )
        return CasePage(items, next_cursor)

    def get_case(self, actor_user_id: uuid.UUID, case_id: uuid.UUID) -> CaseDetail:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._reader(repositories, actor_user_id)
            case = repositories.cases.get(case_id)
            if case is None or (actor.role is UserRole.OPERATOR and case.owner_user_id != actor.id):
                raise CaseNotFoundError("Case was not found.")
            owner = repositories.users.get(case.owner_user_id)
            assert owner is not None
            results = repositories.case_results.for_case(case.id)
            tracks = {
                track.id: track
                for track, _, _ in repositories.tracks.with_location(
                    {row.track_id for row in results}
                )
            }
            return CaseDetail(
                _summary(case, owner, len(results)),
                [_result_view(row, tracks.get(row.track_id)) for row in results],
            )

    def viewer_dashboard(
        self, actor_user_id: uuid.UUID, *, recent_limit: int = 10
    ) -> ViewerDashboard:
        if recent_limit < 1 or recent_limit > MAX_RECENT_CASES:
            raise InvalidCaseRequestError(f"recent_limit must be between 1 and {MAX_RECENT_CASES}.")
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._active(repositories, actor_user_id)
            if actor.role is not UserRole.VIEWER:
                raise CaseAccessDeniedError("Only a Viewer can open the dashboard.")
            recent = repositories.cases.recent_with_owner(limit=recent_limit)
            counts = repositories.case_results.count_by_case(case.id for case, _ in recent)
            by_status = repositories.cases.count_by_status()
            return ViewerDashboard(
                open_cases=by_status.get(CaseStatus.OPEN, 0),
                closed_cases=by_status.get(CaseStatus.CLOSED, 0),
                total_cases=repositories.cases.count(),
                total_case_results=repositories.case_results.count(),
                recent_cases=[
                    _summary(case, owner, counts.get(case.id, 0)) for case, owner in recent
                ],
            )

    def viewer_operators(self, actor_user_id: uuid.UUID) -> list[CaseOwnerView]:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            actor = self._active(repositories, actor_user_id)
            if actor.role is not UserRole.VIEWER:
                raise CaseAccessDeniedError("Only a Viewer can list Case owners.")
            return [
                CaseOwnerView(owner.id, owner.display_name, owner.status)
                for owner in repositories.cases.owners()
            ]

    def _save_track(
        self,
        repositories: Repositories,
        actor: User,
        case: Case,
        track_id: uuid.UUID,
        now: datetime,
    ) -> tuple[CaseResult, PersonTrack]:
        rows = repositories.tracks.with_location([track_id])
        if not rows:
            raise TrackNotSavableError("Track is not available to this Operator.")
        track, camera, area = rows[0]
        if (
            track.index_status is not TrackIndexStatus.READY
            or camera.area_id != actor.assigned_area_id
            or camera.status is not CameraStatus.ACTIVE
        ):
            raise TrackNotSavableError("Track is not available to this Operator.")
        result = CaseResult(
            id=uuid.uuid4(),
            case_id=case.id,
            track_id=track.id,
            camera_name_snapshot=camera.name,
            area_name_snapshot=area.name,
            appeared_at_snapshot=track.appeared_at_utc,
            saved_at=now,
        )
        repositories.case_results.add(result)
        return result, track

    def _active(self, repositories: Repositories, actor_user_id: uuid.UUID) -> User:
        actor = repositories.users.get(actor_user_id)
        if actor is None or actor.status is not UserStatus.ACTIVE:
            raise CaseAccessDeniedError("Actor is not an active user.")
        return actor

    def _reader(self, repositories: Repositories, actor_user_id: uuid.UUID) -> User:
        actor = self._active(repositories, actor_user_id)
        if actor.role not in (UserRole.OPERATOR, UserRole.VIEWER):
            raise CaseAccessDeniedError("Only an Operator or Viewer can read Cases.")
        return actor

    def _operator(
        self,
        repositories: Repositories,
        actor_user_id: uuid.UUID,
        event: AuditEvent,
        case_id: uuid.UUID | None,
    ) -> User:
        actor = self._active(repositories, actor_user_id)
        try:
            owner_id_from_authenticated_actor(actor.id, actor.role)
        except CaseOwnerNotAllowedError as error:
            self._audit_denied(actor, event, case_id, "role_not_allowed")
            raise CaseAccessDeniedError("Only an Operator can change Cases.") from error
        return actor

    def _owned_case(
        self,
        repositories: Repositories,
        actor: User,
        case_id: uuid.UUID,
        event: AuditEvent,
    ) -> Case:
        case = repositories.cases.get_for_update(case_id)
        if case is None:
            raise CaseNotFoundError("Case was not found.")
        if case.owner_user_id != actor.id:
            self._audit_denied(actor, event, case_id, "not_owner")
            raise CaseNotFoundError("Case was not found.")
        return case

    def _audit_denied(
        self, actor: User, event: AuditEvent, case_id: uuid.UUID | None, reason: str
    ) -> None:
        if self._audit is not None:
            self._audit.record_standalone(
                event_type=event,
                result=AuditResult.FAILURE,
                target_type="case",
                target_id=case_id,
                actor=actor,
                metadata={"reason": reason},
            )

    @staticmethod
    def _repositories(work: UnitOfWork) -> Repositories:
        assert work.repositories is not None
        return work.repositories
