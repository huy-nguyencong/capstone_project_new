from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from auth_fakes import PASSWORD, START, AuthWorld
from storage_fakes import FakeDatabase, FakeUnitOfWork

from person_search import create_app
from person_search.dependencies import DependencyContainer
from person_search.services.audit import AuditRecorder
from person_search.services.cases import CaseService
from person_search.services.track_imagery import TrackImage, TrackImageNotFoundError
from person_search.storage.postgres.models import PersonTrack, TrackIndexStatus, UserRole

pytestmark = [pytest.mark.unit, pytest.mark.contract]


class FakeImages:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.calls: list[tuple[uuid.UUID, uuid.UUID | None]] = []

    def case_result_image(self, actor_id, case_result_id, variant, *, case_id=None):
        self.calls.append((case_result_id, case_id))
        row = self.database.case_results.get(case_result_id)
        if row is None or row.case_id != case_id:
            raise TrackImageNotFoundError("missing")
        return TrackImage(b"jpeg", 1, 1)


class Env:
    def __init__(self) -> None:
        self.world = AuthWorld()
        self.operator = self.world.user("operator", UserRole.OPERATOR)
        self.other = self.world.user("other", UserRole.OPERATOR)
        self.viewer = self.world.user("viewer", UserRole.VIEWER)
        self.admin = self.world.user("admin", UserRole.ADMIN)
        self.database = database = FakeDatabase()
        database.users = self.world.database.users
        database.areas = self.world.database.areas
        self.camera_id = uuid.uuid4()
        database.cameras[self.camera_id] = SimpleNamespace(
            id=self.camera_id, area_id=self.world.area.id, name="Cổng chính"
        )
        self.track_id = self._track()
        self.images = FakeImages(database)

        def unit_of_work() -> FakeUnitOfWork:
            return FakeUnitOfWork(database)

        self.container = container = DependencyContainer()
        container.register("auth.service", self.world.service)
        container.register(
            "cases.service",
            CaseService(unit_of_work, audit=AuditRecorder(unit_of_work)),  # type: ignore[arg-type]
        )
        container.register("track_images.service", self.images)
        self.app = create_app({"TESTING": True}, dependencies=container)

    def _track(self) -> uuid.UUID:
        track_id = uuid.uuid4()
        self.database.tracks[track_id] = PersonTrack(
            id=track_id,
            camera_id=self.camera_id,
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            appeared_at_utc=START - timedelta(hours=1),
            source_started_at_ms=0,
            source_ended_at_ms=1_000,
            representative_frame_timestamp_ms=500,
            bbox_x=10,
            bbox_y=20,
            bbox_width=30,
            bbox_height=60,
            frame_width=1920,
            frame_height=1080,
            minio_object_key="tracks/v1/key.jpg",
            frame_sha256="a" * 64,
            frame_size_bytes=10,
            encoder_version="fake_demo_v1",
            vector_indexed_at=START,
            index_status=TrackIndexStatus.READY,
        )
        return track_id

    def client(self, username: str = "operator"):
        client = self.app.test_client()
        response = client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
        )
        csrf = response.get_json()["csrf_token"]
        client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
        return client


def test_operator_case_lifecycle_contract() -> None:
    env = Env()
    client = env.client()

    created = client.post(
        "/api/v1/cases",
        json={"title": "  Hành lý  ", "note": "ghi chú", "track_id": str(env.track_id)},
    )
    assert created.status_code == 201
    body = created.get_json()
    case = body["case"]
    assert case["title"] == "Hành lý"
    assert case["owner"] == {
        "id": str(env.operator.id),
        "display_name": "Operator",
        "status": "ACTIVE",
    }
    assert case["result_count"] == 1 and case["version"] == 1
    first = body["results"][0]
    assert first["track_id"] == str(env.track_id)
    assert first["bbox"]["frame_width"] == 1920
    assert "matching_score" not in first
    assert first["crop_url"] == f"/api/v1/cases/{case['id']}/results/{first['id']}/crop"

    added = client.post(f"/api/v1/cases/{case['id']}/results", json={"track_id": str(env.track_id)})
    assert added.status_code == 201

    listed = client.get("/api/v1/cases?limit=10")
    assert listed.status_code == 200
    assert listed.get_json()["items"][0]["result_count"] == 2
    assert listed.get_json()["next_cursor"] is None

    patched = client.patch(
        f"/api/v1/cases/{case['id']}", json={"title": "Mới", "note": None, "version": 1}
    )
    assert patched.status_code == 200
    assert patched.get_json()["version"] == 2 and patched.get_json()["note"] is None

    stale = client.patch(f"/api/v1/cases/{case['id']}", json={"title": "Cũ", "version": 1})
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "version_conflict"

    removed = client.delete(f"/api/v1/cases/{case['id']}/results/{first['id']}")
    assert removed.status_code == 204
    detail = client.get(f"/api/v1/cases/{case['id']}").get_json()
    assert detail["case"]["result_count"] == 1
    assert env.track_id in env.database.tracks

    crop = client.get(detail["results"][0]["crop_url"])
    assert crop.status_code == 200
    assert crop.headers["Cache-Control"] == "private, no-store"
    assert env.images.calls[-1][1] == uuid.UUID(case["id"])


def test_patch_rejects_forbidden_fields_and_missing_version() -> None:
    env = Env()
    client = env.client()
    case_id = client.post("/api/v1/cases", json={"title": "A"}).get_json()["case"]["id"]

    forbidden = client.patch(
        f"/api/v1/cases/{case_id}", json={"owner_user_id": str(env.other.id), "version": 1}
    )
    assert forbidden.status_code == 422
    assert "owner_user_id" in forbidden.get_json()["error"]["details"]["field_errors"]

    missing = client.patch(f"/api/v1/cases/{case_id}", json={"title": "B"})
    assert missing.status_code == 422

    blank = client.patch(f"/api/v1/cases/{case_id}", json={"title": "  ", "version": 1})
    assert blank.status_code == 422


def test_other_operator_sees_404_and_viewer_is_read_only() -> None:
    env = Env()
    owner = env.client()
    case = owner.post(
        "/api/v1/cases", json={"title": "A", "track_id": str(env.track_id)}
    ).get_json()
    case_id = case["case"]["id"]
    result_id = case["results"][0]["id"]

    other = env.client("other")
    assert other.get(f"/api/v1/cases/{case_id}").status_code == 404
    assert other.get("/api/v1/cases").get_json()["items"] == []
    assert (
        other.post(
            f"/api/v1/cases/{case_id}/results", json={"track_id": str(env.track_id)}
        ).status_code
        == 404
    )

    viewer = env.client("viewer")
    listed = viewer.get(f"/api/v1/cases?owner_user_id={env.operator.id}")
    assert [item["id"] for item in listed.get_json()["items"]] == [case_id]
    assert viewer.get(f"/api/v1/cases/{case_id}").status_code == 200
    assert viewer.get(f"/api/v1/cases/{case_id}/results/{result_id}/frame").status_code == 200
    assert viewer.post("/api/v1/cases", json={"title": "x"}).status_code == 403
    assert (
        viewer.patch(f"/api/v1/cases/{case_id}", json={"title": "x", "version": 1}).status_code
        == 403
    )
    assert viewer.delete(f"/api/v1/cases/{case_id}/results/{result_id}").status_code == 403

    admin = env.client("admin")
    assert admin.get("/api/v1/cases").status_code == 403


def test_track_outside_area_and_media_from_another_case() -> None:
    env = Env()
    client = env.client()
    foreign_area = uuid.uuid4()
    env.database.areas[foreign_area] = SimpleNamespace(id=foreign_area, name="B")
    env.database.cameras[env.camera_id].area_id = foreign_area

    denied = client.post("/api/v1/cases", json={"title": "A", "track_id": str(env.track_id)})
    assert denied.status_code == 403
    assert denied.get_json()["error"]["code"] == "track_not_savable"
    assert client.get("/api/v1/cases").get_json()["items"] == []

    env.database.cameras[env.camera_id].area_id = env.world.area.id
    first = client.post(
        "/api/v1/cases", json={"title": "A", "track_id": str(env.track_id)}
    ).get_json()
    second = client.post("/api/v1/cases", json={"title": "B"}).get_json()
    wrong = client.get(
        f"/api/v1/cases/{second['case']['id']}/results/{first['results'][0]['id']}/crop"
    )
    assert wrong.status_code == 404
    assert wrong.get_json()["error"]["code"] == "case_result_not_found"


def test_list_validates_query() -> None:
    env = Env()
    client = env.client()
    assert client.get("/api/v1/cases?limit=0").status_code == 422
    assert client.get("/api/v1/cases?cursor=bad!").status_code == 422
    assert client.get("/api/v1/cases?created_from=yesterday").status_code == 422
    assert (
        client.get("/api/v1/cases?created_from=2026-09-26&created_to=2026-09-25").status_code == 422
    )
