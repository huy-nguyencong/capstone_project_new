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
    CameraStatus,
    PersonTrack,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

ALLOWED_TOP_K = frozenset({4, 8, 12, 16})
# A re-ranking stage may ask for a larger candidate pool (ef is raised to the pool size).
MAX_POOL = 128
# Stale or out-of-scope hits are dropped after hydration; when that leaves fewer than
# top_k results, Milvus is queried again with a doubled limit (top_k, 2x, 4x).
MAX_SEARCH_ROUNDS = 3


class SearchNotAllowedError(PermissionError):
    pass


class CameraOutOfScopeError(PermissionError):
    pass


class InvalidSearchRequestError(ValueError):
    pass


class CameraNotActiveError(InvalidSearchRequestError):
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
    frame_object_key: str | None = None


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

    def search(
        self, actor_user_id: uuid.UUID, query: TrackSearchQuery, *, pool: int | None = None
    ) -> list[TrackSearchResult]:
        """Up to ``top_k`` results, or up to ``pool`` candidates for a re-ranking stage."""

        if isinstance(query.top_k, bool) or query.top_k not in ALLOWED_TOP_K:
            raise InvalidSearchRequestError("top_k must be one of 4, 8, 12, or 16.")
        if pool is not None and (
            isinstance(pool, bool)
            or not isinstance(pool, int)
            or not query.top_k <= pool <= MAX_POOL
        ):
            raise InvalidSearchRequestError(f"pool must be between top_k and {MAX_POOL}.")
        wanted = pool or query.top_k
        camera_ids = tuple(dict.fromkeys(query.camera_ids))
        area_id, active_cameras = self._authorize(actor_user_id, camera_ids)
        # Tracks of inactive/retired cameras are kept but not searchable until reactivated.
        scope = camera_ids or active_cameras
        if not scope:
            return []
        try:
            filters = VectorFilter(
                area_id=area_id,
                appeared_from=query.appeared_from,
                appeared_to=query.appeared_to,
                camera_ids=scope,
            )
        except ValueError as error:
            raise InvalidSearchRequestError(str(error)) from error

        limit = wanted
        for _ in range(MAX_SEARCH_ROUNDS):
            hits = self._vector_search(query.embedding, filters, min(limit, MAX_POOL))
            results, stale = self._hydrate(hits, area_id=area_id, query=query, cameras=scope)
            if len(results) >= wanted or len(hits) < min(limit, MAX_POOL) or limit >= MAX_POOL:
                break
            limit *= 2
        self.metrics.searches += 1
        if stale:
            self.metrics.stale_hits += stale
            logger.warning(
                "vector search returned stale or out-of-scope hits",
                extra={"stale_hits": stale, "actor_user_id": str(actor_user_id)},
            )
        return results[:wanted]

    def _vector_search(
        self, embedding: Sequence[float], filters: VectorFilter, limit: int
    ) -> list[VectorSearchHit]:
        try:
            return self._vectors.search(embedding, filters, top_k=limit)
        except InvalidVectorError as error:
            raise InvalidSearchRequestError("Query embedding is invalid.") from error
        except Exception as error:
            if self._storage_metrics is not None:
                self._storage_metrics.record_error(StorageComponent.MILVUS, error)
            raise

    def _hydrate(
        self,
        hits: list[VectorSearchHit],
        *,
        area_id: uuid.UUID,
        query: TrackSearchQuery,
        cameras: tuple[uuid.UUID, ...],
    ) -> tuple[list[TrackSearchResult], int]:
        if not hits:
            return [], 0
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
            if row is None or not _in_scope(*row, area_id=area_id, query=query, cameras=cameras):
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
                    frame_object_key=track.minio_object_key,
                )
            )
        return results, stale

    def _authorize(
        self, actor_user_id: uuid.UUID, camera_ids: tuple[uuid.UUID, ...]
    ) -> tuple[uuid.UUID, tuple[uuid.UUID, ...]]:
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
                if camera.status is not CameraStatus.ACTIVE:
                    raise CameraNotActiveError("Camera is not in operation.")
            return area_id, tuple(repositories.cameras.active_ids_in_area(area_id))

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
    if camera.status is not CameraStatus.ACTIVE:
        return False
    if cameras and camera.id not in cameras:
        return False
    if query.appeared_from is not None and track.appeared_at_utc < query.appeared_from:
        return False
    if query.appeared_to is not None and track.appeared_at_utc > query.appeared_to:
        return False
    return True
