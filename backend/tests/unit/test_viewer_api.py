from __future__ import annotations

import pytest
from test_cases_api import Env

from person_search.storage.postgres.models import UserStatus

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def test_viewer_dashboard_and_operators_contract() -> None:
    env = Env()
    operator = env.client()
    first = operator.post(
        "/api/v1/cases", json={"title": "A", "track_id": str(env.track_id)}
    ).get_json()["case"]
    operator.post(f"/api/v1/cases/{first['id']}/results", json={"track_id": str(env.track_id)})
    operator.post("/api/v1/cases", json={"title": "B"})
    env.database.users[env.operator.id].status = UserStatus.LOCKED

    viewer = env.client("viewer")
    dashboard = viewer.get("/api/v1/viewer/dashboard?recent_limit=1")
    assert dashboard.status_code == 200
    body = dashboard.get_json()
    assert body["total_cases"] == 2
    assert body["total_case_results"] == 2
    assert len(body["recent_cases"]) == 1
    assert body["recent_cases"][0]["owner"]["status"] == "LOCKED"

    operators = viewer.get("/api/v1/viewer/operators")
    assert operators.status_code == 200
    assert operators.get_json()["items"] == [
        {"id": str(env.operator.id), "display_name": "Operator", "status": "LOCKED"}
    ]


def test_viewer_routes_reject_other_roles_and_bad_limit() -> None:
    env = Env()
    viewer = env.client("viewer")
    assert viewer.get("/api/v1/viewer/dashboard?recent_limit=0").status_code == 422
    assert viewer.get("/api/v1/viewer/dashboard?recent_limit=x").status_code == 422
    for username in ("operator", "admin"):
        client = env.client(username)
        assert client.get("/api/v1/viewer/dashboard").status_code == 403
        assert client.get("/api/v1/viewer/operators").status_code == 403
