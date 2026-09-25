"""Small, permission-aware repositories over SQLAlchemy sessions."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import (
    AIConfigVersion,
    Area,
    AuditLog,
    Camera,
    Case,
    CaseResult,
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
        self.case_results = Repository(session, CaseResult)
        self.audit_logs = Repository(session, AuditLog)
