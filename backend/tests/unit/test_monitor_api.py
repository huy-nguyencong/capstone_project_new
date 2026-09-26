from __future__ import annotations

import uuid

import pytest
from storage_fakes import FakeUnitOfWork
from test_cases_api import Env

from person_search.services.audit import AuditLogService

pytestmark = [pytest.mark.unit, pytest.mark.contract]


class FakeMonitoring:
    def __init__(self) -> None:
        self.cameras: list[uuid.UUID] = []

    def system_status(self):
        return {"generated_at": "2026-09-25T08:00:00Z", "summary": {"healthy": 1}}

    def camera_pipeline(self, camera_id, actor_id=None):
        self.cameras.append(camera_id)
        return {"ran_at": "2026-09-25T08:00:00Z", "overall": "SUCCESS", "steps": []}

    def search_components(self, actor_id=None):
        return {"ran_at": "2026-09-25T08:00:00Z", "overall": "FAILED", "steps": []}


def _env() -> tuple[Env, FakeMonitoring]:
    env = Env()
    monitoring = FakeMonitoring()
    env.container.register("monitoring.service", monitoring)
    env.container.register("audit.service", AuditLogService(lambda: FakeUnitOfWork(env.database)))
    return env, monitoring


def test_audit_logs_expose_labels_actor_and_filters() -> None:
    env, _ = _env()
    operator = env.client()
    case_id = operator.post("/api/v1/cases", json={"title": "Hành lý"}).get_json()["case"]["id"]
    operator.patch(f"/api/v1/cases/{case_id}", json={"title": "Mới", "version": 1})

    admin = env.client("admin")
    response = admin.get("/api/v1/admin/audit-logs?event_type=case.created&limit=10")
    assert response.status_code == 200
    [item] = response.get_json()["items"]
    assert item["event_type"] == "case.created"
    assert item["actor"] == {"id": str(env.operator.id), "username": "operator"}
    assert item["target_type"] == "case" and item["target_label"] == "Mới"
    assert item["result"] == "SUCCESS"

    both = admin.get("/api/v1/admin/audit-logs?event_type=case.created&event_type=case.updated")
    assert len(both.get_json()["items"]) == 2

    actors = admin.get("/api/v1/admin/audit-logs/actors").get_json()["items"]
    assert str(env.operator.id) in {actor["id"] for actor in actors}

    assert admin.get("/api/v1/admin/audit-logs?event_type=nope").status_code == 422
    assert admin.get("/api/v1/admin/audit-logs?result=MAYBE").status_code == 422
    assert admin.get("/api/v1/admin/audit-logs?limit=0").status_code == 422
    assert (
        admin.get(
            "/api/v1/admin/audit-logs?occurred_from=2026-09-26&occurred_to=2026-09-25"
        ).status_code
        == 422
    )


def test_status_and_diagnostics_routes() -> None:
    env, monitoring = _env()
    admin = env.client("admin")

    assert admin.get("/api/v1/admin/system-status").get_json()["summary"] == {"healthy": 1}
    camera_id = uuid.uuid4()
    pipeline = admin.post(
        "/api/v1/admin/diagnostics/camera-pipeline", json={"camera_id": str(camera_id)}
    )
    assert pipeline.status_code == 200 and monitoring.cameras == [camera_id]
    assert (
        admin.post("/api/v1/admin/diagnostics/camera-pipeline", json={"camera_id": "x"}).status_code
        == 422
    )
    assert admin.post("/api/v1/admin/diagnostics/search-components").status_code == 200


@pytest.mark.parametrize("username", ["operator", "viewer"])
def test_monitor_routes_are_admin_only(username: str) -> None:
    env, _ = _env()
    client = env.client(username)
    for method, path in (
        ("get", "/api/v1/admin/system-status"),
        ("post", "/api/v1/admin/diagnostics/search-components"),
        ("get", "/api/v1/admin/audit-logs"),
        ("get", "/api/v1/admin/audit-logs/actors"),
    ):
        assert getattr(client, method)(path).status_code == 403
