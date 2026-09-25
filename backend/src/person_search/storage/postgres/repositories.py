"""Small, permission-aware repositories over SQLAlchemy sessions."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import Select, and_, exists, or_, select, update
from sqlalchemy.orm import Session

from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import (
    AIConfigVersion,
    Area,
    AuditLog,
    Camera,
    Case,
    CaseResult,
    OutboxStatus,
    PersonTrack,
    ProcessingJob,
    StorageOutboxEvent,
    TrackIndexStatus,
    User,
    UserRole,
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


class Repositories:
    """Repository registry used by one UnitOfWork transaction."""

    def __init__(self, session: Session) -> None:
        self.areas = Repository(session, Area)
        self.users = Repository(session, User)
        self.cameras = CameraRepository(session)
        self.ai_configs = Repository(session, AIConfigVersion)
        self.jobs = Repository(session, ProcessingJob)
        self.tracks = PersonTrackRepository(session)
        self.outbox = StorageOutboxRepository(session)
        self.cases = CaseRepository(session)
        self.case_results = CaseResultRepository(session)
        self.audit_logs = Repository(session, AuditLog)
