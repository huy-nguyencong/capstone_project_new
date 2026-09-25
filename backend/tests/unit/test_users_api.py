from __future__ import annotations

import uuid

import pytest
from auth_fakes import PASSWORD, AuthUnitOfWork, AuthWorld
from flask import Flask

from person_search import create_app
from person_search.dependencies import DependencyContainer
from person_search.services.users import UserService
from person_search.storage.postgres.models import UserRole, UserStatus

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def build_app(world: AuthWorld) -> Flask:
    container = DependencyContainer()
    container.register("auth.service", world.service)
    container.register(
        "users.service",
        UserService(
            lambda: AuthUnitOfWork(world.database),  # type: ignore[arg-type,return-value]
            hasher=world.hasher,
            clock=world.clock,
        ),
    )
    return create_app({"TESTING": True}, dependencies=container)


@pytest.fixture
def world() -> AuthWorld:
    value = AuthWorld()
    value.admin = value.user("admin", UserRole.ADMIN)  # type: ignore[attr-defined]
    value.operator = value.user("khoa.tran", UserRole.OPERATOR)  # type: ignore[attr-defined]
    value.viewer = value.user("lan.nguyen", UserRole.VIEWER)  # type: ignore[attr-defined]
    value.locked = value.user(  # type: ignore[attr-defined]
        "hung.le", UserRole.OPERATOR, status=UserStatus.LOCKED
    )
    return value


@pytest.fixture
def app(world: AuthWorld) -> Flask:
    return build_app(world)


@pytest.fixture
def api(app: Flask):  # type: ignore[no-untyped-def]
    return app.test_client()


def login(api, username: str = "admin") -> str:  # type: ignore[no-untyped-def]
    response = api.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def test_areas_are_available_to_admin_and_operator(app: Flask) -> None:
    admin_api = app.test_client()
    login(admin_api)
    response = admin_api.get("/api/v1/areas")
    assert response.status_code == 200
    assert response.get_json()["items"][0]["code"] == "GATE-A"

    operator_api = app.test_client()
    login(operator_api, "khoa.tran")
    assert operator_api.get("/api/v1/areas").status_code == 200

    viewer_api = app.test_client()
    login(viewer_api, "lan.nguyen")
    assert viewer_api.get("/api/v1/areas").status_code == 403


def test_users_list_requires_admin_and_supports_filters_and_cursor(app: Flask) -> None:
    api = app.test_client()
    login(api)

    first = api.get("/api/v1/admin/users", query_string={"role": "OPERATOR", "limit": 1})
    assert first.status_code == 200
    assert len(first.get_json()["items"]) == 1
    assert first.get_json()["next_cursor"]
    assert first.get_json()["items"][0]["area"]["code"] == "GATE-A"
    assert set(first.get_json()["items"][0]) == {
        "id",
        "username",
        "display_name",
        "role",
        "status",
        "area",
        "last_login_at",
        "created_at",
        "version",
    }

    second = api.get(
        "/api/v1/admin/users",
        query_string={
            "role": "OPERATOR",
            "limit": 1,
            "cursor": first.get_json()["next_cursor"],
        },
    )
    assert second.status_code == 200
    assert second.get_json()["items"][0]["id"] != first.get_json()["items"][0]["id"]

    search = api.get("/api/v1/admin/users", query_string={"q": "LAN"})
    assert [item["username"] for item in search.get_json()["items"]] == ["lan.nguyen"]


def test_non_admin_cannot_list_users(app: Flask) -> None:
    api = app.test_client()
    login(api, "khoa.tran")
    assert api.get("/api/v1/admin/users").status_code == 403


def test_create_user_requires_csrf_and_returns_created_resource(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api)
    payload = {
        "username": "new.operator",
        "display_name": "New Operator",
        "password": "a-secure-password",
        "role": "OPERATOR",
        "area_id": str(world.area.id),
    }
    assert api.post("/api/v1/admin/users", json=payload).status_code == 403

    response = api.post(
        "/api/v1/admin/users", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 201
    assert response.get_json()["username"] == "new.operator"
    assert response.get_json()["version"] == 1
    password_hash = next(
        user.password_hash
        for user in world.database.users.values()
        if user.username == "new.operator"
    )
    assert world.hasher.verify(
        password_hash,
        payload["password"],
    )
    assert world.database.audit_logs[-1].event_type == "user.created"


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"area_id": None}, "operator_area_required"),
        ({"role": "VIEWER"}, "viewer_area_forbidden"),
    ],
)
def test_create_user_enforces_role_area_rules(api, world: AuthWorld, patch, code) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api)
    payload = {
        "username": "new.user",
        "display_name": "New User",
        "password": "a-secure-password",
        "role": "OPERATOR",
        "area_id": str(world.area.id),
        **patch,
    }
    response = api.post(
        "/api/v1/admin/users", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == code


def test_duplicate_username_returns_contract_error(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api)
    response = api.post(
        "/api/v1/admin/users",
        json={
            "username": "khoa.tran",
            "display_name": "Duplicate",
            "password": "a-secure-password",
            "role": "OPERATOR",
            "area_id": str(world.area.id),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "username_taken"


def test_update_uses_version_and_revokes_target_sessions(app: Flask, world: AuthWorld) -> None:
    target_api = app.test_client()
    login(target_api, "khoa.tran")
    admin_api = app.test_client()
    csrf = login(admin_api)
    target = world.operator  # type: ignore[attr-defined]

    payload = {
        "display_name": "Khoa Updated",
        "role": "VIEWER",
        "area_id": None,
        "version": 1,
    }
    response = admin_api.patch(
        f"/api/v1/admin/users/{target.id}",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.get_json()["version"] == 2
    assert response.get_json()["role"] == "VIEWER"
    assert world.database.audit_logs[-1].event_type == "user.role_changed"
    assert target_api.get("/api/v1/auth/me").status_code == 401

    conflict = admin_api.patch(
        f"/api/v1/admin/users/{target.id}",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "version_conflict"


def test_lock_unlock_deactivate_and_self_protection(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api)
    operator = world.operator  # type: ignore[attr-defined]
    headers = {"X-CSRF-Token": csrf}

    locked = api.post(f"/api/v1/admin/users/{operator.id}/lock", headers=headers)
    assert locked.status_code == 200
    assert locked.get_json()["status"] == "LOCKED"

    unlocked = api.post(f"/api/v1/admin/users/{operator.id}/unlock", headers=headers)
    assert unlocked.status_code == 200
    assert unlocked.get_json()["status"] == "ACTIVE"

    deactivated = api.post(f"/api/v1/admin/users/{operator.id}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.get_json()["status"] == "INACTIVE"
    status_events = [
        item for item in world.database.audit_logs if item.event_type == "user.status_changed"
    ]
    assert len(status_events) == 3

    admin = world.admin  # type: ignore[attr-defined]
    rejected = api.post(f"/api/v1/admin/users/{admin.id}/lock", headers=headers)
    assert rejected.status_code == 409
    assert rejected.get_json()["error"]["code"] == "cannot_lock_self"


def test_unknown_user_and_invalid_cursor_return_json_errors(api) -> None:  # type: ignore[no-untyped-def]
    login(api)
    missing = api.get(f"/api/v1/admin/users/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.get_json()["error"]["code"] == "user_not_found"

    cursor = api.get("/api/v1/admin/users", query_string={"cursor": "%%%"})
    assert cursor.status_code == 422
    assert cursor.get_json()["error"]["code"] == "invalid_cursor"
