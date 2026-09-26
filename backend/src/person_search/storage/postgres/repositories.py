"""Small, permission-aware repositories over SQLAlchemy sessions."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import Select, and_, exists, func, or_, select, tuple_, update
from sqlalchemy.orm import Session

from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    Area,
    AuditLog,
    AuditResult,
    AuthSession,
    Camera,
    CameraStatus,
    Case,
    CaseResult,
    OutboxStatus,
    PersonTrack,
    ProcessingJob,
    StorageOutboxEvent,
    TrackIndexStatus,
    User,
    UserRole,
    UserStatus,
)

ModelT = TypeVar("ModelT")


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: uuid.UUID
    role: UserRole
    area_id: uuid.UUID | None


class Repository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, entity: ModelT) -> None:
        self.session.add(entity)

    def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def page(self, *, limit: int = 50, after_id: uuid.UUID | None = None) -> list[ModelT]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        statement: Select[tuple[ModelT]] = select(self.model).order_by(self.model.id)  # type: ignore[attr-defined]
        if after_id is not None:
            statement = statement.where(self.model.id > after_id)  # type: ignore[attr-defined]
        return list(self.session.scalars(statement.limit(limit)))


class UserRepository(Repository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.session.scalars(statement).one_or_none()

    def search(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        query: str | None = None,
        after_id: uuid.UUID | None = None,
        limit: int = 21,
    ) -> list[User]:
        statement = select(User).order_by(User.id)
        if role is not None:
            statement = statement.where(User.role == role)
        if status is not None:
            statement = statement.where(User.status == status)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(User.username.ilike(pattern), User.display_name.ilike(pattern))
            )
        if after_id is not None:
            statement = statement.where(User.id > after_id)
        return list(self.session.scalars(statement.limit(limit)))

    def update_if_version(
        self, user_id: uuid.UUID, *, expected_version: int, values: dict[str, object]
    ) -> bool:
        result = self.session.execute(
            update(User)
            .where(User.id == user_id, User.version == expected_version)
            .values(**values, version=User.version + 1)
        )
        return result.rowcount == 1

    def refresh(self, user: User) -> None:
        self.session.refresh(user)


class AuthSessionRepository(Repository[AuthSession]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuthSession)

    def get_by_token_hash(
        self, token_hash: str, *, for_update: bool = False
    ) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.token_hash == token_hash)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def revoke_for_user(self, user_id: uuid.UUID, *, at: datetime, reason: str) -> int:
        result = self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=at, revoke_reason=reason)
        )
        return int(result.rowcount or 0)


class CameraRepository(Repository[Camera]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Camera)

    def page_for_actor(self, actor: ActorContext, *, limit: int = 50) -> list[Camera]:
        statement = select(Camera).order_by(Camera.id).limit(limit)
        if actor.role is UserRole.OPERATOR:
            if actor.area_id is None:
                return []
            statement = statement.where(Camera.area_id == actor.area_id)
        return list(self.session.scalars(statement))

    def active_ids_in_area(self, area_id: uuid.UUID) -> list[uuid.UUID]:
        statement = (
            select(Camera.id)
            .where(Camera.area_id == area_id, Camera.status == CameraStatus.ACTIVE)
            .order_by(Camera.id)
        )
        return list(self.session.scalars(statement))


class CaseRepository(Repository[Case]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Case)

    def page_for_actor(self, actor: ActorContext, *, limit: int = 50) -> list[Case]:
        statement = select(Case).order_by(Case.id).limit(limit)
        if actor.role is UserRole.OPERATOR:
            statement = statement.where(Case.owner_user_id == actor.user_id)
        return list(self.session.scalars(statement))

    def rename_if_unchanged(
        self, case_id: uuid.UUID, *, title: str, expected_updated_at: object
    ) -> None:
        result = self.session.execute(
            update(Case)
            .where(Case.id == case_id, Case.updated_at == expected_updated_at)
            .values(title=title)
        )
        if result.rowcount != 1:
            raise ConcurrentUpdateError("Case was changed by another transaction.")

    def refresh(self, case: Case) -> None:
        self.session.refresh(case, ["updated_at"])

    def get_for_update(self, case_id: uuid.UUID) -> Case | None:
        return self.session.scalars(
            select(Case).where(Case.id == case_id).with_for_update()
        ).one_or_none()

    def list_page(
        self,
        *,
        owner_user_id: uuid.UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 51,
    ) -> list[tuple[Case, User]]:
        statement = (
            select(Case, User)
            .join(User, User.id == Case.owner_user_id)
            .order_by(Case.created_at.desc(), Case.id.desc())
        )
        if owner_user_id is not None:
            statement = statement.where(Case.owner_user_id == owner_user_id)
        if created_from is not None:
            statement = statement.where(Case.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(Case.created_at <= created_to)
        if after is not None:
            statement = statement.where(tuple_(Case.created_at, Case.id) < after)
        return [(case, owner) for case, owner in self.session.execute(statement.limit(limit))]

    def recent_with_owner(self, *, limit: int) -> list[tuple[Case, User]]:
        statement = (
            select(Case, User)
            .join(User, User.id == Case.owner_user_id)
            .order_by(Case.updated_at.desc(), Case.id.desc())
            .limit(limit)
        )
        return [(case, owner) for case, owner in self.session.execute(statement)]

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Case)) or 0)

    def owners(self) -> list[User]:
        statement = (
            select(User)
            .where(User.id.in_(select(Case.owner_user_id).distinct()))
            .order_by(User.display_name, User.id)
        )
        return list(self.session.scalars(statement))


class PersonTrackRepository(Repository[PersonTrack]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PersonTrack)

    def get_for_update(self, track_id: uuid.UUID) -> PersonTrack | None:
        return self.session.scalars(
            select(PersonTrack).where(PersonTrack.id == track_id).with_for_update()
        ).one_or_none()

    def ready_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        candidates = list(track_ids)
        if not candidates:
            return set()
        return set(
            self.session.scalars(
                select(PersonTrack.id).where(
                    PersonTrack.id.in_(candidates),
                    PersonTrack.index_status == TrackIndexStatus.READY,
                )
            )
        )

    def existing_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        candidates = list(track_ids)
        if not candidates:
            return set()
        return set(
            self.session.scalars(select(PersonTrack.id).where(PersonTrack.id.in_(candidates)))
        )

    def with_location(
        self, track_ids: Iterable[uuid.UUID]
    ) -> list[tuple[PersonTrack, Camera, Area]]:
        candidates = list(track_ids)
        if not candidates:
            return []
        statement = (
            select(PersonTrack, Camera, Area)
            .join(Camera, Camera.id == PersonTrack.camera_id)
            .join(Area, Area.id == Camera.area_id)
            .where(PersonTrack.id.in_(candidates))
        )
        return [(track, camera, area) for track, camera, area in self.session.execute(statement)]

    def page_by_status(
        self,
        status: TrackIndexStatus,
        *,
        limit: int = 100,
        after_id: uuid.UUID | None = None,
    ) -> list[PersonTrack]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        statement = (
            select(PersonTrack)
            .where(PersonTrack.index_status == status)
            .order_by(PersonTrack.id)
            .limit(limit)
        )
        if after_id is not None:
            statement = statement.where(PersonTrack.id > after_id)
        return list(self.session.scalars(statement))

    def count_by_status(self) -> dict[TrackIndexStatus, int]:
        rows = self.session.execute(
            select(PersonTrack.index_status, func.count()).group_by(PersonTrack.index_status)
        )
        return {status: count for status, count in rows}

    def stale_unready(self, *, updated_before: datetime, limit: int = 100) -> list[PersonTrack]:
        statement = (
            select(PersonTrack)
            .where(
                PersonTrack.index_status.in_(
                    (TrackIndexStatus.PENDING, TrackIndexStatus.FAILED)
                ),
                PersonTrack.updated_at < updated_before,
            )
            .order_by(PersonTrack.updated_at, PersonTrack.id)
            .limit(limit)
        )
        return list(self.session.scalars(statement))


class StorageOutboxRepository(Repository[StorageOutboxEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StorageOutboxEvent)

    def get_for_track(
        self, track_id: uuid.UUID, event_type: str, *, for_update: bool = False
    ) -> StorageOutboxEvent | None:
        statement = select(StorageOutboxEvent).where(
            StorageOutboxEvent.track_id == track_id,
            StorageOutboxEvent.event_type == event_type,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalars(statement).one_or_none()

    def count_by_status(self) -> dict[OutboxStatus, int]:
        rows = self.session.execute(
            select(StorageOutboxEvent.status, func.count()).group_by(StorageOutboxEvent.status)
        )
        return {status: count for status, count in rows}

    def oldest_due_available_at(self, *, now: datetime) -> datetime | None:
        return self.session.scalar(
            select(func.min(StorageOutboxEvent.available_at)).where(
                StorageOutboxEvent.status == OutboxStatus.PENDING,
                StorageOutboxEvent.available_at <= now,
            )
        )

    def claim_due(
        self,
        event_type: str,
        *,
        now: datetime,
        lock_expired_before: datetime,
        limit: int,
    ) -> list[StorageOutboxEvent]:
        statement = (
            select(StorageOutboxEvent)
            .where(
                StorageOutboxEvent.event_type == event_type,
                or_(
                    and_(
                        StorageOutboxEvent.status == OutboxStatus.PENDING,
                        StorageOutboxEvent.available_at <= now,
                    ),
                    and_(
                        StorageOutboxEvent.status == OutboxStatus.PROCESSING,
                        StorageOutboxEvent.locked_at < lock_expired_before,
                    ),
                ),
            )
            .order_by(StorageOutboxEvent.available_at, StorageOutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        events = list(self.session.scalars(statement))
        for event in events:
            event.status = OutboxStatus.PROCESSING
            event.locked_at = now
        return events


class CaseResultRepository(Repository[CaseResult]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CaseResult)

    def for_case(self, case_id: uuid.UUID) -> list[CaseResult]:
        return list(
            self.session.scalars(
                select(CaseResult)
                .where(CaseResult.case_id == case_id)
                .order_by(CaseResult.saved_at, CaseResult.id)
            )
        )

    def delete(self, entity: CaseResult) -> None:
        self.session.delete(entity)

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(CaseResult)) or 0)

    def count_by_case(self, case_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        candidates = list(case_ids)
        if not candidates:
            return {}
        statement = (
            select(CaseResult.case_id, func.count())
            .where(CaseResult.case_id.in_(candidates))
            .group_by(CaseResult.case_id)
        )
        return {case_id: int(total) for case_id, total in self.session.execute(statement)}

    def exists_for_case_track(self, case_id: uuid.UUID, track_id: uuid.UUID) -> bool:
        return bool(
            self.session.scalar(
                select(
                    exists().where(
                        CaseResult.case_id == case_id, CaseResult.track_id == track_id
                    )
                )
            )
        )

    def referenced_track_ids(self, track_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        candidates = list(track_ids)
        if not candidates:
            return set()
        return set(
            self.session.scalars(
                select(CaseResult.track_id).where(CaseResult.track_id.in_(candidates)).distinct()
            )
        )


class AuditLogRepository(Repository[AuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLog)

    def search(
        self,
        *,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        actor_user_id: uuid.UUID | None = None,
        event_types: tuple[str, ...] = (),
        result: AuditResult | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 51,
    ) -> list[AuditLog]:
        statement = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        if occurred_from is not None:
            statement = statement.where(AuditLog.occurred_at >= occurred_from)
        if occurred_to is not None:
            statement = statement.where(AuditLog.occurred_at <= occurred_to)
        if actor_user_id is not None:
            statement = statement.where(AuditLog.actor_user_id == actor_user_id)
        if event_types:
            statement = statement.where(AuditLog.event_type.in_(event_types))
        if result is not None:
            statement = statement.where(AuditLog.result == result)
        if after is not None:
            statement = statement.where(tuple_(AuditLog.occurred_at, AuditLog.id) < after)
        return list(self.session.scalars(statement.limit(limit)))

    def actor_ids(self) -> list[uuid.UUID]:
        return list(
            self.session.scalars(
                select(AuditLog.actor_user_id).where(AuditLog.actor_user_id.is_not(None)).distinct()
            )
        )


class AIConfigRepository(Repository[AIConfigVersion]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AIConfigVersion)

    def active(self) -> AIConfigVersion | None:
        return self.session.scalars(
            select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
        ).one_or_none()


class Repositories:
    """Repository registry used by one UnitOfWork transaction."""

    def __init__(self, session: Session) -> None:
        self.areas = Repository(session, Area)
        self.users = UserRepository(session)
        self.auth_sessions = AuthSessionRepository(session)
        self.cameras = CameraRepository(session)
        self.ai_configs = AIConfigRepository(session)
        self.jobs = Repository(session, ProcessingJob)
        self.tracks = PersonTrackRepository(session)
        self.outbox = StorageOutboxRepository(session)
        self.cases = CaseRepository(session)
        self.case_results = CaseResultRepository(session)
        self.audit_logs = AuditLogRepository(session)
