from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from storage_fakes import FakeDatabase, FakeUnitOfWork

from person_search.services.audit import AuditRecorder
from person_search.services.cases import (
    CaseAccessDeniedError,
    CaseClosedError,
    CaseListQuery,
    CaseNotFoundError,
    CaseService,
    InvalidCaseRequestError,
    TrackNotSavableError,
)
from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import (
    AuditResult,
    CameraStatus,
    CaseStatus,
    PersonTrack,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)

pytestmark = pytest.mark.unit

START = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


class World:
    def __init__(self) -> None:
        self.database = database = FakeDatabase()
        ticks = itertools.count()
        self.clock = lambda: START + timedelta(seconds=next(ticks))
        self.area_a, self.area_b = uuid.uuid4(), uuid.uuid4()
        database.areas[self.area_a] = SimpleNamespace(id=self.area_a, name="Area A")
        database.areas[self.area_b] = SimpleNamespace(id=self.area_b, name="Area B")
        self.camera_a, self.camera_b = uuid.uuid4(), uuid.uuid4()
        database.cameras[self.camera_a] = SimpleNamespace(
            id=self.camera_a, area_id=self.area_a, name="Gate A", status=CameraStatus.ACTIVE
        )
        database.cameras[self.camera_b] = SimpleNamespace(
            id=self.camera_b, area_id=self.area_b, name="Gate B", status=CameraStatus.ACTIVE
        )
        self.operator = self.user(UserRole.OPERATOR, self.area_a, "op-a")
        self.other_operator = self.user(UserRole.OPERATOR, self.area_a, "op-other")
        self.viewer = self.user(UserRole.VIEWER, None, "viewer")
        self.admin = self.user(UserRole.ADMIN, None, "admin")
        self.track_a = self.track(self.camera_a)
        self.track_b = self.track(self.camera_b)

        def unit_of_work() -> FakeUnitOfWork:
            return FakeUnitOfWork(database)

        self.service = CaseService(
            unit_of_work,  # type: ignore[arg-type]
            audit=AuditRecorder(unit_of_work),  # type: ignore[arg-type]
            clock=self.clock,
        )

    def user(
        self,
        role: UserRole,
        area_id: uuid.UUID | None,
        username: str,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> uuid.UUID:
        user_id = uuid.uuid4()
        self.database.users[user_id] = SimpleNamespace(
            id=user_id,
            username=username,
            display_name=username.upper(),
            role=role,
            status=status,
            assigned_area_id=area_id,
        )
        return user_id

    def track(
        self, camera_id: uuid.UUID, status: TrackIndexStatus = TrackIndexStatus.READY
    ) -> uuid.UUID:
        track_id = uuid.uuid4()
        self.database.tracks[track_id] = PersonTrack(
            id=track_id,
            camera_id=camera_id,
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            appeared_at_utc=START - timedelta(hours=1),
            source_started_at_ms=0,
            source_ended_at_ms=1_000,
            representative_frame_timestamp_ms=500,
            bbox_x=1,
            bbox_y=1,
            bbox_width=10,
            bbox_height=20,
            frame_width=64,
            frame_height=48,
            minio_object_key="tracks/v1/key.jpg",
            frame_sha256="a" * 64,
            frame_size_bytes=10,
            encoder_version="rasa_cuhk_pedes_v1",
            vector_indexed_at=START if status is TrackIndexStatus.READY else None,
            index_status=status,
        )
        return track_id

    def events(self) -> list[tuple[str, AuditResult]]:
        return [(entry.event_type, entry.result) for entry in self.database.audit_logs]


def test_create_case_takes_owner_from_session_and_audits() -> None:
    world = World()

    detail = world.service.create_case(world.operator, title="  Lost child  ", note="red shirt")

    case = world.database.cases[detail.case.id]
    assert case.owner_user_id == world.operator
    assert detail.case.title == "Lost child"
    assert detail.case.owner_display_name == "OP-A"
    assert detail.results == []
    assert not hasattr(case, "matching_score")
    assert not hasattr(case, "area_id")
    assert case.status is CaseStatus.OPEN and case.closed_at is None
    assert detail.case.status is CaseStatus.OPEN
    entry = world.database.audit_logs[-1]
    assert entry.event_type == "case.created"
    assert entry.actor_user_id == world.operator
    assert entry.event_metadata["actor"] == {"username": "op-a", "role": "OPERATOR"}
    assert "red shirt" not in str(entry.event_metadata)


def test_closed_case_is_locked_until_reopened_and_audited() -> None:
    world = World()
    detail = world.service.create_case(world.operator, title="Case", track_id=world.track_a)
    case_id, [first] = detail.case.id, detail.results

    closed = world.service.update_case(
        world.operator, case_id, status=CaseStatus.CLOSED, expected_version=1
    )
    assert closed.status is CaseStatus.CLOSED and closed.closed_at is not None
    assert world.events()[-1] == ("case.closed", AuditResult.SUCCESS)

    with pytest.raises(CaseClosedError):
        world.service.add_result(world.operator, case_id, world.track_a)
    with pytest.raises(CaseClosedError):
        world.service.remove_result(world.operator, case_id, first.id)
    with pytest.raises(CaseClosedError):
        world.service.update_case(world.operator, case_id, title="New", expected_version=2)

    reopened = world.service.update_case(
        world.operator, case_id, status=CaseStatus.OPEN, expected_version=2
    )
    assert reopened.status is CaseStatus.OPEN and reopened.closed_at is None
    assert world.events()[-1] == ("case.reopened", AuditResult.SUCCESS)
    world.service.add_result(world.operator, case_id, world.track_a)
    assert world.service.get_case(world.viewer, case_id).case.result_count == 2


def test_case_list_filters_by_status_and_dashboard_counts_them() -> None:
    world = World()
    open_id = world.service.create_case(world.operator, title="Open").case.id
    closed_id = world.service.create_case(world.operator, title="Done").case.id
    world.service.update_case(
        world.operator, closed_id, status=CaseStatus.CLOSED, expected_version=1
    )

    page = world.service.list_cases(world.operator, CaseListQuery(status=CaseStatus.OPEN))
    assert [item.id for item in page.items] == [open_id]
    dashboard = world.service.viewer_dashboard(world.viewer)
    assert (dashboard.open_cases, dashboard.closed_cases) == (1, 1)


def test_create_case_with_initial_track_snapshots_server_metadata() -> None:
    world = World()

    detail = world.service.create_case(world.operator, title="Case", track_id=world.track_a)

    [result] = detail.results
    assert result.track_id == world.track_a
    assert result.camera_name == "Gate A"
    assert result.area_name == "Area A"
    assert result.appeared_at == START - timedelta(hours=1)
    assert not hasattr(world.database.case_results[result.id], "matching_score")


def test_create_case_with_foreign_track_rolls_back_everything() -> None:
    world = World()

    with pytest.raises(TrackNotSavableError):
        world.service.create_case(world.operator, title="Case", track_id=world.track_b)

    assert world.database.cases == {}
    assert world.database.case_results == {}
    assert world.database.audit_logs == []


@pytest.mark.parametrize("actor", ["viewer", "admin"])
def test_only_operator_can_create_case_and_denial_is_audited(actor: str) -> None:
    world = World()

    with pytest.raises(CaseAccessDeniedError):
        world.service.create_case(getattr(world, actor), title="Case")

    assert world.database.cases == {}
    assert world.events() == [("case.created", AuditResult.FAILURE)]


def test_locked_operator_cannot_create_case() -> None:
    world = World()
    locked = world.user(UserRole.OPERATOR, world.area_a, "locked", UserStatus.LOCKED)

    with pytest.raises(CaseAccessDeniedError):
        world.service.create_case(locked, title="Case")


def test_saving_same_track_twice_creates_two_results() -> None:
    world = World()
    case_id = world.service.create_case(world.operator, title="Case").case.id

    first = world.service.add_result(world.operator, case_id, world.track_a)
    second = world.service.add_result(world.operator, case_id, world.track_a)

    assert first.id != second.id
    assert first.track_id == second.track_id
    assert len(world.service.get_case(world.operator, case_id).results) == 2
    dashboard = world.service.viewer_dashboard(world.viewer)
    assert dashboard.total_case_results == 2


def test_adding_to_another_operators_case_is_hidden_and_audited() -> None:
    world = World()
    case_id = world.service.create_case(world.other_operator, title="Theirs").case.id

    with pytest.raises(CaseNotFoundError):
        world.service.add_result(world.operator, case_id, world.track_a)

    assert world.database.case_results == {}
    denied = world.database.audit_logs[-1]
    assert denied.event_type == "case.result_added"
    assert denied.result is AuditResult.FAILURE
    assert denied.event_metadata["reason"] == "not_owner"


def test_unready_or_foreign_track_cannot_be_saved() -> None:
    world = World()
    case_id = world.service.create_case(world.operator, title="Case").case.id
    pending = world.track(world.camera_a, TrackIndexStatus.PENDING)

    for track_id in (world.track_b, pending, uuid.uuid4()):
        with pytest.raises(TrackNotSavableError):
            world.service.add_result(world.operator, case_id, track_id)


def test_track_of_inactive_camera_cannot_be_saved_but_saved_results_stay() -> None:
    world = World()
    case_id = world.service.create_case(
        world.operator, title="Case", track_id=world.track_a
    ).case.id
    world.database.cameras[world.camera_a].status = CameraStatus.RETIRED

    with pytest.raises(TrackNotSavableError):
        world.service.add_result(world.operator, case_id, world.track_a)
    detail = world.service.get_case(world.operator, case_id)
    assert [result.track_id for result in detail.results] == [world.track_a]


def test_operator_keeps_case_after_area_change_but_saves_only_new_area() -> None:
    world = World()
    case_id = world.service.create_case(
        world.operator, title="Case", track_id=world.track_a
    ).case.id
    world.database.users[world.operator].assigned_area_id = world.area_b

    detail = world.service.get_case(world.operator, case_id)
    page = world.service.list_cases(world.operator, CaseListQuery())

    assert [result.area_name for result in detail.results] == ["Area A"]
    assert [item.id for item in page.items] == [case_id]
    with pytest.raises(TrackNotSavableError):
        world.service.add_result(world.operator, case_id, world.track_a)
    added = world.service.add_result(world.operator, case_id, world.track_b)
    assert added.area_name == "Area B"


def test_viewer_reads_every_case_but_cannot_change_it() -> None:
    world = World()
    mine = world.service.create_case(world.operator, title="Mine").case.id
    theirs = world.service.create_case(world.other_operator, title="Theirs").case.id

    page = world.service.list_cases(world.viewer, CaseListQuery())
    filtered = world.service.list_cases(
        world.viewer, CaseListQuery(owner_user_id=world.other_operator)
    )

    assert {item.id for item in page.items} == {mine, theirs}
    assert [item.id for item in filtered.items] == [theirs]
    assert world.service.get_case(world.viewer, mine).case.title == "Mine"
    with pytest.raises(CaseAccessDeniedError):
        world.service.update_case(world.viewer, mine, title="Changed")
    with pytest.raises(CaseAccessDeniedError):
        world.service.add_result(world.viewer, mine, world.track_a)


def test_operator_list_ignores_owner_filter_for_other_operators() -> None:
    world = World()
    world.service.create_case(world.other_operator, title="Theirs")

    page = world.service.list_cases(
        world.operator, CaseListQuery(owner_user_id=world.other_operator)
    )

    assert page.items == []
    with pytest.raises(CaseAccessDeniedError):
        world.service.list_cases(world.admin, CaseListQuery())


def test_operator_cannot_read_another_operators_case() -> None:
    world = World()
    theirs = world.service.create_case(world.other_operator, title="Theirs").case.id

    with pytest.raises(CaseNotFoundError):
        world.service.get_case(world.operator, theirs)


def test_removing_one_duplicate_keeps_the_other_and_the_track() -> None:
    world = World()
    case_id = world.service.create_case(world.operator, title="Case").case.id
    first = world.service.add_result(world.operator, case_id, world.track_a)
    second = world.service.add_result(world.operator, case_id, world.track_a)

    world.service.remove_result(world.operator, case_id, first.id)

    remaining = world.service.get_case(world.operator, case_id).results
    assert [result.id for result in remaining] == [second.id]
    assert world.track_a in world.database.tracks
    with pytest.raises(CaseNotFoundError):
        world.service.remove_result(world.operator, case_id, first.id)
    assert world.events()[-1] == ("case.result_removed", AuditResult.SUCCESS)


def test_result_from_another_case_cannot_be_removed_through_this_case() -> None:
    world = World()
    case_one = world.service.create_case(world.operator, title="One").case.id
    case_two = world.service.create_case(world.operator, title="Two").case.id
    result = world.service.add_result(world.operator, case_two, world.track_a)

    with pytest.raises(CaseNotFoundError):
        world.service.remove_result(world.operator, case_one, result.id)

    assert result.id in world.database.case_results


def test_update_case_validates_and_detects_concurrent_changes() -> None:
    world = World()
    created = world.service.create_case(world.operator, title="Old", note="n").case

    updated = world.service.update_case(
        world.operator,
        created.id,
        title="New",
        note=None,
        expected_updated_at=created.updated_at,
    )

    assert updated.title == "New" and updated.note is None
    assert world.database.audit_logs[-1].event_metadata["changed_fields"] == ["note", "title"]
    with pytest.raises(ConcurrentUpdateError):
        world.service.update_case(
            world.operator, created.id, title="Stale", expected_updated_at=created.updated_at
        )
    with pytest.raises(InvalidCaseRequestError):
        world.service.update_case(world.operator, created.id, title="   ")
    with pytest.raises(InvalidCaseRequestError):
        world.service.update_case(world.operator, created.id)
    with pytest.raises(InvalidCaseRequestError):
        world.service.create_case(world.operator, title="x" * 201)


def test_case_list_pagination_is_stable() -> None:
    world = World()
    created = [
        world.service.create_case(world.operator, title=f"Case {index}").case.id
        for index in range(5)
    ]

    first = world.service.list_cases(world.operator, CaseListQuery(limit=2))
    second = world.service.list_cases(
        world.operator, CaseListQuery(limit=2, cursor=first.next_cursor)
    )
    third = world.service.list_cases(
        world.operator, CaseListQuery(limit=2, cursor=second.next_cursor)
    )

    seen = [item.id for page in (first, second, third) for item in page.items]
    assert seen == list(reversed(created))
    assert third.next_cursor is None
    with pytest.raises(InvalidCaseRequestError):
        world.service.list_cases(world.operator, CaseListQuery(cursor="not-a-cursor"))


def test_viewer_dashboard_counts_rows_and_lists_recent_cases() -> None:
    world = World()
    empty = world.service.viewer_dashboard(world.viewer)
    older = world.service.create_case(world.operator, title="Older").case.id
    newer = world.service.create_case(world.other_operator, title="Newer").case.id
    world.service.add_result(world.operator, older, world.track_a)
    world.service.add_result(world.operator, older, world.track_a)

    dashboard = world.service.viewer_dashboard(world.viewer, recent_limit=5)

    assert (empty.total_cases, empty.total_case_results, empty.recent_cases) == (0, 0, [])
    assert dashboard.total_cases == 2
    assert dashboard.total_case_results == 2
    assert [item.id for item in dashboard.recent_cases] == [older, newer]
    assert dashboard.recent_cases[0].owner_display_name == "OP-A"
    for actor in (world.operator, world.admin):
        with pytest.raises(CaseAccessDeniedError):
            world.service.viewer_dashboard(actor)


def test_cases_of_locked_operator_remain_visible_to_viewer() -> None:
    world = World()
    case_id = world.service.create_case(world.operator, title="Case").case.id
    world.database.users[world.operator].status = UserStatus.LOCKED

    assert world.service.get_case(world.viewer, case_id).case.owner_user_id == world.operator
    with pytest.raises(CaseAccessDeniedError):
        world.service.get_case(world.operator, case_id)


def test_version_increments_and_stale_version_is_rejected() -> None:
    world = World()
    created = world.service.create_case(world.operator, title="Old").case
    assert created.version == 1

    updated = world.service.update_case(
        world.operator, created.id, title="New", expected_version=1
    )

    assert updated.version == 2
    with pytest.raises(ConcurrentUpdateError):
        world.service.update_case(world.operator, created.id, title="Stale", expected_version=1)
    assert world.database.cases[created.id].title == "New"


def test_summaries_carry_result_count_owner_status_and_bbox() -> None:
    world = World()
    case_id = world.service.create_case(
        world.operator, title="Case", track_id=world.track_a
    ).case.id
    world.service.add_result(world.operator, case_id, world.track_a)
    world.service.create_case(world.operator, title="Empty")
    world.database.users[world.operator].status = UserStatus.LOCKED

    page = world.service.list_cases(world.viewer, CaseListQuery())
    detail = world.service.get_case(world.viewer, case_id)
    dashboard = world.service.viewer_dashboard(world.viewer)

    counts = {item.title: item.result_count for item in page.items}
    assert counts == {"Case": 2, "Empty": 0}
    assert page.items[0].owner_status is UserStatus.LOCKED
    assert detail.case.result_count == 2
    assert detail.results[0].bbox is not None
    assert (detail.results[0].bbox.width, detail.results[0].bbox.frame_width) == (10, 64)
    assert {item.title: item.result_count for item in dashboard.recent_cases} == counts


def test_viewer_operators_lists_every_case_owner_including_locked() -> None:
    world = World()
    world.service.create_case(world.operator, title="A")
    world.service.create_case(world.operator, title="B")
    world.database.users[world.operator].status = UserStatus.LOCKED

    owners = world.service.viewer_operators(world.viewer)

    assert [(owner.id, owner.status) for owner in owners] == [
        (world.operator, UserStatus.LOCKED)
    ]
    for actor in (world.operator, world.admin):
        with pytest.raises(CaseAccessDeniedError):
            world.service.viewer_operators(actor)
