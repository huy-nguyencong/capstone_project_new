from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from person_search.services.storage_status import StorageComponent, StorageMetrics
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.milvus.vectors import InvalidVectorError, VectorFilter, VectorSearchHit
from person_search.storage.postgres.models import (
    Area,
    Camera,
    PersonTrack,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

ALLOWED_TOP_K = frozenset({4, 8, 12, 16})


class SearchNotAllowedError(PermissionError):
    pass


class CameraOutOfScopeError(PermissionError):
    pass


class InvalidSearchRequestError(ValueError):
    pass


class VectorSearcher(Protocol):
    def search(
        self, vector: Sequence[float], filters: VectorFilter, *, top_k: int
    ) -> list[VectorSearchHit]: ...


@dataclass(frozen=True, slots=True)
class TrackSearchQuery:
    embedding: Sequence[float]
    top_k: int
    camera_ids: tuple[uuid.UUID, ...] = ()
    appeared_from: datetime | None = None
    appeared_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class TrackSearchResult:
    track_id: uuid.UUID
    matching_score: float
    camera_id: uuid.UUID
    camera_name: str
    area_id: uuid.UUID
    area_name: str
    appeared_at_utc: datetime
    bbox: BoundingBoxPixels


@dataclass(slots=True)
class SearchMetrics:
    searches: int = 0
    stale_hits: int = 0


class TrackSearchService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        vectors: VectorSearcher,
        *,
        metrics: SearchMetrics | None = None,
        storage_metrics: StorageMetrics | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._vectors = vectors
        self.metrics = metrics or SearchMetrics()
        self._storage_metrics = storage_metrics

    def search(self, actor_user_id: uuid.UUID, query: TrackSearchQuery) -> list[TrackSearchResult]:
        if isinstance(query.top_k, bool) or query.top_k not in ALLOWED_TOP_K:
            raise InvalidSearchRequestError("top_k must be one of 4, 8, 12, or 16.")
        camera_ids = tuple(dict.fromkeys(query.camera_ids))
        area_id = self._authorize(actor_user_id, camera_ids)
        try:
            filters = VectorFilter(
                area_id=area_id,
                appeared_from=query.appeared_from,
                appeared_to=query.appeared_to,
                camera_ids=camera_ids,
            )
        except ValueError as error:
            raise InvalidSearchRequestError(str(error)) from error
        try:
            hits = self._vectors.search(query.embedding, filters, top_k=query.top_k)
        except InvalidVectorError as error:
            raise InvalidSearchRequestError("Query embedding is invalid.") from error
        except Exception as error:
            if self._storage_metrics is not None:
                self._storage_metrics.record_error(StorageComponent.MILVUS, error)
            raise
        self.metrics.searches += 1
        if not hits:
            return []

        with self._unit_of_work_factory() as work:
            rows = {
                track.id: (track, camera, area)
                for track, camera, area in self._repositories(work).tracks.with_location(
                    hit.track_id for hit in hits
                )
            }

        results: list[TrackSearchResult] = []
        stale = 0
        for hit in hits:
            row = rows.get(hit.track_id)
            if row is None or not _in_scope(*row, area_id=area_id, query=query, cameras=camera_ids):
                stale += 1
                continue
            track, camera, area = row
            results.append(
                TrackSearchResult(
                    track_id=track.id,
                    matching_score=hit.score,
                    camera_id=camera.id,
                    camera_name=camera.name,
                    area_id=area.id,
                    area_name=area.name,
                    appeared_at_utc=track.appeared_at_utc,
                    bbox=BoundingBoxPixels(
                        x=track.bbox_x,
                        y=track.bbox_y,
                        width=track.bbox_width,
                        height=track.bbox_height,
                        frame_width=track.frame_width,
                        frame_height=track.frame_height,
                    ),
                )
            )
        if stale:
            self.metrics.stale_hits += stale
            logger.warning(
                "vector search returned stale or out-of-scope hits",
                extra={"stale_hits": stale, "actor_user_id": str(actor_user_id)},
            )
        return results

    def _authorize(self, actor_user_id: uuid.UUID, camera_ids: tuple[uuid.UUID, ...]) -> uuid.UUID:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            user = repositories.users.get(actor_user_id)
            if (
                user is None
                or user.status is not UserStatus.ACTIVE
                or user.role is not UserRole.OPERATOR
                or user.assigned_area_id is None
            ):
                raise SearchNotAllowedError("Only an active Operator with an area can search.")
            area_id = user.assigned_area_id
            for camera_id in camera_ids:
                camera = repositories.cameras.get(camera_id)
                if camera is None or camera.area_id != area_id:
                    raise CameraOutOfScopeError("Camera is outside the Operator's current area.")
            return area_id

    @staticmethod
    def _repositories(work: UnitOfWork) -> Repositories:
        assert work.repositories is not None
        return work.repositories


def _in_scope(
    track: PersonTrack,
    camera: Camera,
    area: Area,
    *,
    area_id: uuid.UUID,
    query: TrackSearchQuery,
    cameras: tuple[uuid.UUID, ...],
) -> bool:
    if track.index_status is not TrackIndexStatus.READY:
        return False
    if camera.area_id != area_id or area.id != area_id or track.camera_id != camera.id:
        return False
    if cameras and camera.id not in cameras:
        return False
    if query.appeared_from is not None and track.appeared_at_utc < query.appeared_from:
        return False
    if query.appeared_to is not None and track.appeared_at_utc > query.appeared_to:
        return False
    return True
