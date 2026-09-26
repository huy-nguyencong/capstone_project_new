from __future__ import annotations

import uuid

import pytest
from auth_fakes import PASSWORD, AuthWorld

from person_search import create_app
from person_search.dependencies import DependencyContainer
from person_search.services.searches import OperatorCamera, SearchResponse
from person_search.services.track_search import CameraNotActiveError, TrackSearchResult
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.postgres.models import UserRole

pytestmark = [pytest.mark.unit, pytest.mark.contract]


class FakeSearchService:
    def __init__(self, world: AuthWorld) -> None:
        self.world = world
        self.camera_id = uuid.uuid4()
        self.track_id = uuid.uuid4()

    def cameras(self, actor_id):
        return (OperatorCamera(self.camera_id, "A-01", "Cổng chính", True),)

    def search_text(self, actor_id, text, **filters):
        if self.camera_id not in filters.get("camera_ids", ()) and filters.get("camera_ids"):
            raise CameraNotActiveError("Camera is not in operation.")
        return SearchResponse(
            "TEXT",
            text,
            "fake_demo_v1",
            filters["top_k"],
            (
                TrackSearchResult(
                    self.track_id,
                    0.91,
                    self.camera_id,
                    "Cổng chính",
                    self.world.area.id,
                    self.world.area.name,
                    self.world.clock(),
                    BoundingBoxPixels(10, 20, 30, 60, 1920, 1080),
                ),
            ),
        )


def _app():
    world = AuthWorld()
    world.user("operator", UserRole.OPERATOR)
    world.user("viewer", UserRole.VIEWER)
    container = DependencyContainer()
    container.register("auth.service", world.service)
    search = FakeSearchService(world)
    container.register("searches.service", search)
    app = create_app({"TESTING": True}, dependencies=container)
    return app, search


def _login(client, username="operator"):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    return response.get_json()["csrf_token"]


def test_operator_camera_and_text_search_contract() -> None:
    app, search = _app()
    client = app.test_client()
    csrf = _login(client)

    cameras = client.get("/api/v1/me/cameras")
    assert cameras.status_code == 200
    assert cameras.get_json()["items"][0]["id"] == str(search.camera_id)

    response = client.post(
        "/api/v1/searches/text",
        json={"text": "person in red", "top_k": 8, "camera_ids": []},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "TEXT"
    assert body["results"][0]["crop_url"].endswith(f"/{search.track_id}/crop")
    assert body["results"][0]["bbox"]["frame_width"] == 1920


def test_search_rejects_invalid_top_k_and_non_operator() -> None:
    app, _ = _app()
    operator = app.test_client()
    csrf = _login(operator)
    invalid = operator.post(
        "/api/v1/searches/text",
        json={"text": "person in red", "top_k": 24},
        headers={"X-CSRF-Token": csrf},
    )
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "invalid_top_k"

    viewer = app.test_client()
    viewer_csrf = _login(viewer, "viewer")
    forbidden = viewer.post(
        "/api/v1/searches/text",
        json={"text": "person in red", "top_k": 8},
        headers={"X-CSRF-Token": viewer_csrf},
    )
    assert forbidden.status_code == 403


def test_search_filter_on_inactive_camera_is_rejected() -> None:
    app, _ = _app()
    client = app.test_client()
    csrf = _login(client)

    response = client.post(
        "/api/v1/searches/text",
        json={"text": "person in red", "top_k": 8, "camera_ids": [str(uuid.uuid4())]},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "camera_not_active"
