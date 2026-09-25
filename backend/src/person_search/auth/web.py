from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, TypeVar, cast

from flask import Response, current_app, g, request

from person_search.api.errors import ApiError
from person_search.auth.tokens import csrf_matches
from person_search.services.auth import AuthenticatedUser, AuthService, SessionInvalidError
from person_search.storage.postgres.models import UserRole

CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

RouteT = TypeVar("RouteT", bound=Callable[..., Any])


def auth_service() -> AuthService:
    return cast(
        AuthService, current_app.extensions["person_search.dependencies"].get("auth.service")
    )


def session_token() -> str | None:
    return request.cookies.get(current_app.config["AUTH_COOKIE_NAME"]) or None


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    config = current_app.config
    response.set_cookie(
        config["AUTH_COOKIE_NAME"],
        token,
        expires=expires_at,
        path="/",
        secure=config["AUTH_COOKIE_SECURE"],
        httponly=True,
        samesite=config["AUTH_COOKIE_SAMESITE"],
    )


def clear_session_cookie(response: Response) -> None:
    config = current_app.config
    response.delete_cookie(
        config["AUTH_COOKIE_NAME"],
        path="/",
        secure=config["AUTH_COOKIE_SECURE"],
        httponly=True,
        samesite=config["AUTH_COOKIE_SAMESITE"],
    )


def mark_session_cookie_for_clearing() -> None:
    g.clear_session_cookie = True


def clear_rejected_session_cookie(response: Response) -> Response:
    if g.get("clear_session_cookie"):
        clear_session_cookie(response)
    return response


def require_csrf(token: str | None) -> None:
    if request.method in SAFE_METHODS:
        return
    if not csrf_matches(token, request.headers.get(CSRF_HEADER)):
        raise ApiError(403, "csrf_failed", "Phiên làm việc không hợp lệ. Vui lòng tải lại trang.")


def current_actor() -> AuthenticatedUser:
    return cast(AuthenticatedUser, g.actor)


def require_auth(*roles: UserRole) -> Callable[[RouteT], RouteT]:
    allowed = frozenset(roles)

    def decorator(route: RouteT) -> RouteT:
        @wraps(route)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = session_token()
            try:
                actor = auth_service().authenticate(token)
            except SessionInvalidError as error:
                if token:
                    mark_session_cookie_for_clearing()
                if error.reason == "expired":
                    raise ApiError(
                        401,
                        "session_expired",
                        "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.",
                    ) from error
                raise ApiError(401, "unauthenticated", "Vui lòng đăng nhập để tiếp tục.") from error
            require_csrf(token)
            if allowed and actor.role not in allowed:
                raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.")
            g.actor = actor
            return route(*args, **kwargs)

        return cast(RouteT, wrapper)

    return decorator
