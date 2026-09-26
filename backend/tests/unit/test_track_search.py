from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from storage_fakes import FakeDatabase, FakeUnitOfWork

from person_search.services.track_search import (
    MAX_SEARCH_ROUNDS,
    CameraNotActiveError,
    CameraOutOfScopeError,
    InvalidSearchRequestError,
    SearchNotAllowedError,
    TrackSearchQuery,
    TrackSearchService,
)
from person_search.storage.milvus.vectors import InvalidVectorError, VectorFilter, VectorSearchHit
from person_search.storage.postgres.models import (
    CameraStatus,
    PersonTrack,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)
EMBEDDING = [1.0, 0.0, 0.0, 0.0]


class FakeSearcher:
    def __init__(self) -> None:
        self.hits: list[VectorSearchHit] = []
        self.calls: list[tuple[VectorFilter, int]] = []
        self.error: Exception | None = None

    def search(
        self, vector: Sequence[float], filters: VectorFilter, *, top_k: int
    ) -> list[VectorSearchHit]:
        if self.error is not None:
            raise self.error
        self.calls.append((filters, top_k))
        return self.hits[:top_k]


class World:
    def __init__(self) -> None:
        self.database = database = FakeDatabase()
        self.area_a, self.area_b = uuid.uuid4(), uuid.uuid4()
        database.areas[self.area_a] = SimpleNamespace(id=self.area_a, name="Area A")
        database.areas[self.area_b] = SimpleNamespace(id=self.area_b, name="Area B")
        self.camera_a1 = self._camera(self.area_a, "Gate A1")
        self.camera_a2 = self._camera(self.area_a, "Gate A2", CameraStatus.RETIRED)
        self.camera_b = self._camera(self.area_b, "Gate B")
        self.operator = self._user(UserRole.OPERATOR, self.area_a)
        self.searcher = FakeSearcher()
        self.service = TrackSearchService(
            lambda: FakeUnitOfWork(database),  # type: ignore[arg-type,return-value]
            self.searcher,
        )

    def _camera(
        self, area_id: uuid.UUID, name: str, status: CameraStatus = CameraStatus.ACTIVE
    ) -> uuid.UUID:
        camera_id = uuid.uuid4()
        self.database.cameras[camera_id] = SimpleNamespace(
            id=camera_id, area_id=area_id, name=name, status=status
        )
        return camera_id

    def _user(
        self,
        role: UserRole,
        area_id: uuid.UUID | None,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> uuid.UUID:
        user_id = uuid.uuid4()
        self.database.users[user_id] = SimpleNamespace(
            id=user_id, role=role, status=status, assigned_area_id=area_id
        )
        return user_id

    def track(
        self,
        camera_id: uuid.UUID,
        *,
        status: TrackIndexStatus = TrackIndexStatus.READY,
        appeared_at: datetime = NOW,
    ) -> uuid.UUID:
        track_id = uuid.uuid4()
        self.database.tracks[track_id] = PersonTrack(
            id=track_id,
            camera_id=camera_id,
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            appeared_at_utc=appeared_at,
            source_started_at_ms=0,
            source_ended_at_ms=1_000,
            representative_frame_timestamp_ms=500,
            bbox_x=10,
            bbox_y=20,
            bbox_width=30,
            bbox_height=60,
            frame_width=640,
            frame_height=480,
            minio_object_key=f"tracks/v1/{camera_id}/2026/09/25/{track_id}/representative.jpg",
            frame_sha256="a" * 64,
            frame_size_bytes=100,
            encoder_version="rasa_cuhk_pedes_v1",
            vector_indexed_at=NOW if status is TrackIndexStatus.READY else None,
            index_status=status,
        )
        return track_id

    def hits(self, *pairs: tuple[uuid.UUID, float]) -> None:
        self.searcher.hits = [VectorSearchHit(track_id, score) for track_id, score in pairs]


def test_search_scopes_to_operator_area_and_returns_transient_score() -> None:
    world = World()
    first, second = world.track(world.camera_a1), world.track(world.camera_a1)
    world.hits((first, 0.91), (second, 0.72))

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=8))

    assert [result.track_id for result in results] == [first, second]
    assert [result.matching_score for result in results] == [0.91, 0.72]
    assert results[0].camera_name == "Gate A1" and results[0].area_name == "Area A"
    assert results[0].bbox.width == 30
    filters, top_k = world.searcher.calls[0]
    assert top_k == 8
    assert filters.area_id == world.area_a
    assert f'area_id == "{world.area_a}"' in filters.expression()
    assert not hasattr(world.database.tracks[first], "matching_score")


@pytest.mark.parametrize("top_k", [0, 5, 20, True, -4])
def test_top_k_outside_allowed_set_is_rejected(top_k: int) -> None:
    world = World()

    with pytest.raises(InvalidSearchRequestError):
        world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=top_k))

    assert world.searcher.calls == []


def test_camera_from_other_area_is_rejected_before_vector_search() -> None:
    world = World()

    with pytest.raises(CameraOutOfScopeError):
        world.service.search(
            world.operator,
            TrackSearchQuery(EMBEDDING, top_k=4, camera_ids=(world.camera_a1, world.camera_b)),
        )

    assert world.searcher.calls == []


def test_unknown_camera_is_rejected() -> None:
    world = World()

    with pytest.raises(CameraOutOfScopeError):
        world.service.search(
            world.operator, TrackSearchQuery(EMBEDDING, top_k=4, camera_ids=(uuid.uuid4(),))
        )


@pytest.mark.parametrize(
    ("role", "status", "has_area"),
    [
        (UserRole.VIEWER, UserStatus.ACTIVE, False),
        (UserRole.ADMIN, UserStatus.ACTIVE, False),
        (UserRole.OPERATOR, UserStatus.LOCKED, True),
        (UserRole.OPERATOR, UserStatus.INACTIVE, True),
    ],
)
def test_only_active_operator_can_search(
    role: UserRole, status: UserStatus, has_area: bool
) -> None:
    world = World()
    actor = world._user(role, world.area_a if has_area else None, status)

    with pytest.raises(SearchNotAllowedError):
        world.service.search(actor, TrackSearchQuery(EMBEDDING, top_k=4))


def test_unknown_actor_cannot_search() -> None:
    world = World()

    with pytest.raises(SearchNotAllowedError):
        world.service.search(uuid.uuid4(), TrackSearchQuery(EMBEDDING, top_k=4))


def test_area_comes_from_database_after_operator_is_reassigned() -> None:
    world = World()
    world.database.users[world.operator].assigned_area_id = world.area_b
    track_b = world.track(world.camera_b)
    world.hits((track_b, 0.8))

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert [result.track_id for result in results] == [track_b]
    assert world.searcher.calls[0][0].area_id == world.area_b


def test_stale_pending_missing_and_foreign_hits_are_dropped_and_counted() -> None:
    world = World()
    ready = world.track(world.camera_a1)
    pending = world.track(world.camera_a1, status=TrackIndexStatus.PENDING)
    failed = world.track(world.camera_a1, status=TrackIndexStatus.FAILED)
    foreign = world.track(world.camera_b)
    world.hits((foreign, 0.99), (pending, 0.95), (uuid.uuid4(), 0.9), (failed, 0.85), (ready, 0.5))

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=8))

    assert [result.track_id for result in results] == [ready]
    assert world.service.metrics.stale_hits == 4
    assert world.service.metrics.searches == 1


def test_camera_and_time_filters_are_sent_to_vector_search_and_rechecked() -> None:
    world = World()
    inside = world.track(world.camera_a1, appeared_at=NOW)
    other_camera = world.track(world.camera_a2, appeared_at=NOW)
    too_late = world.track(world.camera_a1, appeared_at=NOW + timedelta(hours=2))
    world.hits((other_camera, 0.9), (too_late, 0.8), (inside, 0.7))
    query = TrackSearchQuery(
        EMBEDDING,
        top_k=4,
        camera_ids=(world.camera_a1, world.camera_a1),
        appeared_from=NOW - timedelta(hours=1),
        appeared_to=NOW + timedelta(hours=1),
    )

    results = world.service.search(world.operator, query)

    assert [result.track_id for result in results] == [inside]
    filters = world.searcher.calls[0][0]
    assert filters.camera_ids == (world.camera_a1,)
    expression = filters.expression()
    assert f'camera_id in ["{world.camera_a1}"]' in expression
    assert "appeared_at_epoch >=" in expression and "appeared_at_epoch <=" in expression


def test_inactive_camera_cannot_be_used_as_filter() -> None:
    world = World()

    with pytest.raises(CameraNotActiveError):
        world.service.search(
            world.operator, TrackSearchQuery(EMBEDDING, top_k=4, camera_ids=(world.camera_a2,))
        )

    assert world.searcher.calls == []


def test_tracks_of_inactive_camera_are_kept_but_not_searchable() -> None:
    world = World()
    history = world.track(world.camera_a2)
    live = world.track(world.camera_a1)
    world.hits((history, 0.9), (live, 0.6))

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert [result.track_id for result in results] == [live]
    assert history in world.database.tracks
    filters = world.searcher.calls[0][0]
    assert filters.camera_ids == (world.camera_a1,)


def test_tracks_become_searchable_again_after_camera_is_reactivated() -> None:
    world = World()
    history = world.track(world.camera_a2)
    world.hits((history, 0.9))
    world.database.cameras[world.camera_a2].status = CameraStatus.ACTIVE

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert [result.track_id for result in results] == [history]


def test_area_without_active_camera_returns_empty_without_vector_search() -> None:
    world = World()
    world.database.cameras[world.camera_a1].status = CameraStatus.INACTIVE

    assert world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4)) == []
    assert world.searcher.calls == []


def test_stale_hits_are_refilled_to_reach_top_k() -> None:
    world = World()
    stale = [world.track(world.camera_a1, status=TrackIndexStatus.PENDING) for _ in range(4)]
    ready = [world.track(world.camera_a1) for _ in range(6)]
    world.hits(
        *[(track_id, 0.99 - index * 0.01) for index, track_id in enumerate(stale)],
        *[(track_id, 0.8 - index * 0.01) for index, track_id in enumerate(ready)],
    )

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert [result.track_id for result in results] == ready[:4]
    assert [limit for _, limit in world.searcher.calls] == [4, 8]
    assert world.service.metrics.searches == 1
    assert world.service.metrics.stale_hits == 4


def test_refill_stops_when_scope_is_exhausted() -> None:
    world = World()
    stale = world.track(world.camera_a1, status=TrackIndexStatus.FAILED)
    ready = world.track(world.camera_a1)
    world.hits((stale, 0.9), (ready, 0.8))

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert [result.track_id for result in results] == [ready]
    assert [limit for _, limit in world.searcher.calls] == [4]


def test_refill_rounds_are_bounded() -> None:
    world = World()
    stale = [world.track(world.camera_a1, status=TrackIndexStatus.PENDING) for _ in range(40)]
    world.hits(*[(track_id, 0.5) for track_id in stale])

    results = world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))

    assert results == []
    assert [limit for _, limit in world.searcher.calls] == [4, 8, 16][:MAX_SEARCH_ROUNDS]


def test_naive_time_filter_is_rejected() -> None:
    world = World()

    with pytest.raises(InvalidSearchRequestError):
        world.service.search(
            world.operator,
            TrackSearchQuery(EMBEDDING, top_k=4, appeared_from=datetime(2026, 9, 25)),
        )


def test_invalid_query_embedding_is_rejected() -> None:
    world = World()
    world.searcher.error = InvalidVectorError("bad")

    with pytest.raises(InvalidSearchRequestError):
        world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=4))


def test_empty_vector_result_returns_empty_list() -> None:
    world = World()

    assert world.service.search(world.operator, TrackSearchQuery(EMBEDDING, top_k=16)) == []
