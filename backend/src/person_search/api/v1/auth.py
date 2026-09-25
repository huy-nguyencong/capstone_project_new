from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

from person_search.api.errors import ApiError, validation_error
from person_search.api.rate_limit import client_address, enforce
from person_search.auth.tokens import csrf_token_for
from person_search.auth.web import (
    auth_service,
    clear_session_cookie,
    current_actor,
    raise_session_invalid,
    require_auth,
    require_csrf,
    session_token,
    set_session_cookie,
)
from person_search.services.auth import (
    AccountDisabledError,
    AuthenticatedUser,
    InvalidCredentialsError,
    SessionGrant,
    SessionInvalidError,
)

auth_blueprint = Blueprint("auth", __name__, url_prefix="/auth")


def serialize_user(user: AuthenticatedUser) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "area": (
            {"id": str(user.area.id), "code": user.area.code, "name": user.area.name}
            if user.area is not None
            else None
        ),
    }


def serialize_session(grant: SessionGrant) -> dict[str, Any]:
    return {
        "user": serialize_user(grant.user),
        "csrf_token": csrf_token_for(grant.token),
        "expires_at": grant.expires_at.isoformat(),
        "refresh_after_seconds": auth_service().policy.refresh_after_seconds,
    }


def _login_payload() -> tuple[str, str]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_json", "Request body phải là JSON object.")
    username = body.get("username")
    password = body.get("password")
    field_errors: dict[str, str] = {}
    if not isinstance(username, str) or not username.strip():
        field_errors["username"] = "Vui lòng nhập tên đăng nhập."
    if not isinstance(password, str) or not password:
        field_errors["password"] = "Vui lòng nhập mật khẩu."
    if field_errors:
        raise validation_error(field_errors)
    return username, password


@auth_blueprint.post("/login")
def login():  # type: ignore[no-untyped-def]
    username, password = _login_payload()
    enforce("login", f"{client_address()}|{username.strip().lower()}")
    try:
        grant = auth_service().login(username, password, previous_token=session_token())
    except InvalidCredentialsError as error:
        raise ApiError(
            401,
            "invalid_credentials",
            "Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng nhập lại.",
        ) from error
    except AccountDisabledError as error:
        raise ApiError(
            403,
            "account_disabled",
            "Tài khoản đã bị khóa hoặc ngừng hoạt động và không có quyền truy cập hệ thống. "
            "Liên hệ Admin.",
        ) from error
    response = jsonify(serialize_session(grant))
    set_session_cookie(response, grant.token, grant.expires_at)
    return response


@auth_blueprint.get("/me")
@require_auth()
def me():  # type: ignore[no-untyped-def]
    token = session_token()
    assert token is not None
    return jsonify(
        {
            "user": serialize_user(current_actor()),
            "csrf_token": csrf_token_for(token),
            "refresh_after_seconds": auth_service().policy.refresh_after_seconds,
        }
    )


@auth_blueprint.post("/refresh")
def refresh():  # type: ignore[no-untyped-def]
    token = session_token()
    if token:
        require_csrf(token)
    try:
        grant = auth_service().refresh(token)
    except SessionInvalidError as error:
        raise_session_invalid(error, token)
    response = jsonify(serialize_session(grant))
    set_session_cookie(response, grant.token, grant.expires_at)
    return response


@auth_blueprint.post("/logout")
def logout():  # type: ignore[no-untyped-def]
    token = session_token()
    if token:
        require_csrf(token)
        auth_service().logout(token)
    response = Response(status=204)
    clear_session_cookie(response)
    return response
