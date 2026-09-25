from __future__ import annotations

import re
import uuid

import pytest
from auth_fakes import PASSWORD, AuthWorld
from test_searches_api import FakeSearchService

from person_search import create_app
from person_search.api.rate_limit import FixedWindowLimiter
from person_search.dependencies import DependencyContainer
from person_search.storage.postgres.models import UserRole

pytestmark = [pytest.mark.unit, pytest.mark.security]

ADMIN, OPERATOR, VIEWER = UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER
ANY = frozenset({ADMIN, OPERATOR, VIEWER})

ACCESS: dict[tuple[str, str], frozenset[UserRole] | None] = {
    ("POST", "/api/v1/auth/login"): None,
    ("POST", "/api/v1/auth/logout"): None,
    ("GET", "/api/v1/auth/me"): ANY,
    ("GET", "/api/v1/areas"): frozenset({ADMIN, OPERATOR}),
    ("GET", "/api/v1/me/cameras"): frozenset({OPERATOR}),
    ("POST", "/api/v1/searches/image"): frozenset({OPERATOR}),
    ("POST", "/api/v1/searches/text"): frozenset({OPERATOR}),
    ("POST", "/api/v1/searches/attributes"): frozenset({OPERATOR}),
    ("GET", "/api/v1/search-results/<uuid:track_id>/crop"): frozenset({OPERATOR}),
    ("GET", "/api/v1/search-results/<uuid:track_id>/frame"): frozenset({OPERATOR}),
    ("GET", "/api/v1/cases"): frozenset({OPERATOR, VIEWER}),
    ("POST", "/api/v1/cases"): frozenset({OPERATOR}),
    ("GET", "/api/v1/cases/<uuid:case_id>"): frozenset({OPERATOR, VIEWER}),
    ("PATCH", "/api/v1/cases/<uuid:case_id>"): frozenset({OPERATOR}),
    ("POST", "/api/v1/cases/<uuid:case_id>/results"): frozenset({OPERATOR}),
    (
        "DELETE",
        "/api/v1/cases/<uuid:case_id>/results/<uuid:case_result_id>",
    ): frozenset({OPERATOR}),
    (
        "GET",
        "/api/v1/cases/<uuid:case_id>/results/<uuid:case_result_id>/crop",
    ): frozenset({OPERATOR, VIEWER}),
    (
        "GET",
        "/api/v1/cases/<uuid:case_id>/results/<uuid:case_result_id>/frame",
    ): frozenset({OPERATOR, VIEWER}),
    ("GET", "/api/v1/viewer/dashboard"): frozenset({VIEWER}),
    ("GET", "/api/v1/viewer/operators"): frozenset({VIEWER}),
}

ADMIN_PREFIX = "/api/v1/admin/"


def _app(config=None, *, search=False):
    world = AuthWorld()
    for username, role in (("admin", ADMIN), ("operator", OPERATOR), ("viewer", VIEWER)):
        world.user(username, role)
    container = DependencyContainer()
    container.register("auth.service", world.service)
    if search:
        container.register("searches.service", FakeSearchService(world))
    return create_app({"TESTING": True, **(config or {})}, dependencies=container)


def _login(client, username):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    client.environ_base["HTTP_X_CSRF_TOKEN"] = response.get_json()["csrf_token"]
    return client


def _routes(app):
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/v1/"):
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            yield method, rule.rule


def _concrete(path):
    return re.sub(r"<[^>]+>", lambda _: str(uuid.uuid4()), path)


def _allowed(method, path):
    if path.startswith(ADMIN_PREFIX):
        return frozenset({ADMIN})
    return ACCESS[(method, path)]


def test_every_route_has_a_declared_access_rule() -> None:
    app = _app()
    missing = [
        route
        for route in _routes(app)
        if not route[1].startswith(ADMIN_PREFIX) and route not in ACCESS
    ]
    assert missing == []


def test_permission_matrix_for_every_route() -> None:
    app = _app()
    clients = {role: _login(app.test_client(), role.value.lower()) for role in ANY}
    anonymous = app.test_client()
    failures = []
    for method, path in _routes(app):
        allowed = _allowed(method, path)
        if allowed is None:
            continue
        url = _concrete(path)
        status = anonymous.open(url, method=method).status_code
        if status != 401:
            failures.append((method, path, "anonymous", status))
        for role, client in clients.items():
            status = client.open(url, method=method, json={}).status_code
            denied = status == 403
            if (role in allowed) == denied or status == 401:
                failures.append((method, path, role.value, status))
    assert failures == []


def test_mutations_require_csrf_token() -> None:
    app = _app()
    client = _login(app.test_client(), "operator")
    del client.environ_base["HTTP_X_CSRF_TOKEN"]
    response = client.post("/api/v1/cases", json={"title": "x"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_failed"


def test_login_is_rate_limited_per_address_and_username() -> None:
    app = _app({"RATE_LIMITS": {"login": (3, 60)}})
    client = app.test_client()
    for _ in range(3):
        wrong = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
        assert wrong.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1
    other = client.post("/api/v1/auth/login", json={"username": "viewer", "password": PASSWORD})
    assert other.status_code == 200


def test_search_is_rate_limited_per_actor() -> None:
    app = _app({"RATE_LIMITS": {"search": (2, 60)}}, search=True)
    client = _login(app.test_client(), "operator")
    body = {"text": "person in red", "top_k": 8}
    assert client.post("/api/v1/searches/text", json=body).status_code == 200
    assert client.post("/api/v1/searches/text", json=body).status_code == 200
    assert client.post("/api/v1/searches/text", json=body).status_code == 429


def test_fixed_window_resets_after_window() -> None:
    now = [0.0]
    limiter = FixedWindowLimiter(clock=lambda: now[0])
    assert limiter.hit("b", "k", 1, 10) is None
    assert limiter.hit("b", "k", 1, 10) == pytest.approx(10)
    now[0] = 10.0
    assert limiter.hit("b", "k", 1, 10) is None


def test_security_headers_on_success_and_error() -> None:
    app = _app()
    client = app.test_client()
    for response in (client.get("/health/live"), client.get("/api/v1/auth/me")):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert client.get("/api/v1/auth/me").headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in client.get("/health/live").headers
    secure = _app({"AUTH_COOKIE_SECURE": True}).test_client().get("/health/live")
    assert secure.headers["Strict-Transport-Security"].startswith("max-age=")


def test_cors_only_for_allowlisted_origins() -> None:
    app = _app({"CORS_ORIGINS": ("https://ui.example",)})
    client = app.test_client()
    preflight = client.options(
        "/api/v1/cases",
        headers={
            "Origin": "https://ui.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-CSRF-Token",
        },
    )
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://ui.example"
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"
    assert "X-CSRF-Token" in preflight.headers["Access-Control-Allow-Headers"]

    evil = client.get("/api/v1/auth/me", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in evil.headers
    assert "Origin" in evil.headers["Vary"]
