from __future__ import annotations

from datetime import timedelta

import pytest
from auth_fakes import PASSWORD, AuthWorld
from flask import Flask, jsonify

from person_search import create_app
from person_search.auth.web import current_actor, require_auth
from person_search.dependencies import DependencyContainer
from person_search.storage.postgres.models import UserRole, UserStatus

pytestmark = pytest.mark.unit

COOKIE = "ps_session"


def build_app(world: AuthWorld) -> Flask:
    container = DependencyContainer()
    container.register("auth.service", world.service)
    app = create_app({"TESTING": True}, dependencies=container)

    @app.post("/api/v1/_probe/admin")
    @require_auth(UserRole.ADMIN)
    def admin_probe():  # type: ignore[no-untyped-def]
        return jsonify({"actor": current_actor().username})

    return app


@pytest.fixture
def world() -> AuthWorld:
    world = AuthWorld()
    world.user("admin", UserRole.ADMIN)
    world.user("khoa.tran", UserRole.OPERATOR)
    world.user("lan", UserRole.VIEWER)
    world.user("hung", UserRole.OPERATOR, status=UserStatus.LOCKED)
    return world


@pytest.fixture
def api(world: AuthWorld):  # type: ignore[no-untyped-def]
    return build_app(world).test_client()


def login(api, username: str = "khoa.tran", password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return api.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_sets_http_only_cookie_and_returns_actor(api) -> None:  # type: ignore[no-untyped-def]
    response = login(api)

    assert response.status_code == 200
    body = response.get_json()
    assert body["user"]["username"] == "khoa.tran"
    assert body["user"]["role"] == "OPERATOR"
    assert body["user"]["area"]["code"] == "GATE-A"
    assert set(body["user"]) == {"id", "username", "display_name", "role", "area"}
    assert len(body["csrf_token"]) == 64
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie


def test_secure_cookie_flag_follows_configuration(world: AuthWorld) -> None:
    container = DependencyContainer()
    container.register("auth.service", world.service)
    app = create_app({"TESTING": True, "AUTH_COOKIE_SECURE": True}, dependencies=container)

    response = login(app.test_client())

    assert "Secure" in response.headers["Set-Cookie"]


def test_me_returns_same_actor_and_csrf_token(api) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api).get_json()["csrf_token"]

    response = api.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "khoa.tran"
    assert response.get_json()["csrf_token"] == csrf


@pytest.mark.parametrize(
    ("username", "password"),
    [("khoa.tran", "wrong-password"), ("nobody", PASSWORD)],
)
def test_invalid_credentials_share_one_response(api, username: str, password: str) -> None:  # type: ignore[no-untyped-def]
    response = login(api, username, password)

    assert response.status_code == 401
    error = response.get_json()["error"]
    assert error["code"] == "invalid_credentials"
    assert error["request_id"]
    assert "Set-Cookie" not in response.headers


def test_locked_account_is_rejected(api) -> None:  # type: ignore[no-untyped-def]
    response = login(api, "hung")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "account_disabled"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "", "password": ""},
        {"username": "khoa.tran"},
        {"username": 1, "password": 2},
    ],
)
def test_login_validates_fields(api, payload: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    response = api.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_failed"
    assert response.get_json()["error"]["details"]["field_errors"]


def test_login_rejects_non_json_body(api) -> None:  # type: ignore[no-untyped-def]
    response = api.post("/api/v1/auth/login", data="username=admin")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"


def test_me_requires_session(api) -> None:  # type: ignore[no-untyped-def]
    response = api.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthenticated"


def test_expired_session_returns_specific_code_and_clears_cookie(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    login(api)
    world.clock.advance(minutes=31)

    response = api.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "session_expired"
    assert f"{COOKIE}=;" in response.headers["Set-Cookie"]


def test_logout_requires_csrf_revokes_session_and_clears_cookie(api) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api).get_json()["csrf_token"]

    rejected = api.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    assert rejected.get_json()["error"]["code"] == "csrf_failed"

    response = api.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204
    assert f"{COOKIE}=;" in response.headers["Set-Cookie"]
    assert api.get("/api/v1/auth/me").status_code == 401


def test_logout_without_session_is_idempotent(api) -> None:  # type: ignore[no-untyped-def]
    assert api.post("/api/v1/auth/logout").status_code == 204


def test_revoked_cookie_cannot_be_replayed(api) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api).get_json()["csrf_token"]
    token = api.get_cookie(COOKIE).value
    api.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

    api.set_cookie(COOKIE, token)

    assert api.get("/api/v1/auth/me").status_code == 401


def test_protected_mutation_enforces_csrf_and_role(api) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api, "admin").get_json()["csrf_token"]

    assert api.post("/api/v1/_probe/admin").status_code == 403
    assert api.post("/api/v1/_probe/admin", headers={"X-CSRF-Token": "forged"}).status_code == 403
    response = api.post("/api/v1/_probe/admin", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.get_json() == {"actor": "admin"}


@pytest.mark.parametrize("username", ["khoa.tran", "lan"])
def test_non_admin_roles_are_forbidden(api, username: str) -> None:  # type: ignore[no-untyped-def]
    csrf = login(api, username).get_json()["csrf_token"]

    response = api.post("/api/v1/_probe/admin", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_locking_user_blocks_next_request(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    login(api)
    next(
        user for user in world.database.users.values() if user.username == "khoa.tran"
    ).status = UserStatus.LOCKED

    assert api.get("/api/v1/auth/me").status_code == 401


def test_auth_returns_503_when_storage_is_not_configured(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/v1/auth/login", json={"username": "a", "password": "b"})

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "service_unavailable"


def test_session_lifetime_matches_cookie_expiry(api, world: AuthWorld) -> None:  # type: ignore[no-untyped-def]
    response = login(api)

    expected = world.clock.now + timedelta(hours=12)
    assert expected.strftime("%d %b %Y %H:%M:%S") in response.headers["Set-Cookie"]
