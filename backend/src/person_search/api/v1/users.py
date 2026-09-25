from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from flask import Blueprint, current_app, jsonify, request

from person_search.api.errors import ApiError, validation_error
from person_search.auth.web import current_actor, require_auth
from person_search.services.users import (
    UserConflictError,
    UserListQuery,
    UserNotFoundError,
    UserRequestError,
    UserService,
    UserView,
)
from person_search.storage.postgres.models import UserRole, UserStatus

areas_blueprint = Blueprint("areas", __name__)
admin_users_blueprint = Blueprint("admin_users", __name__, url_prefix="/admin/users")


def user_service() -> UserService:
    return cast(
        UserService,
        current_app.extensions["person_search.dependencies"].get("users.service"),
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_user(user: UserView) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "status": user.status.value,
        "area": (
            {"id": str(user.area.id), "code": user.area.code, "name": user.area.name}
            if user.area
            else None
        ),
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
        "version": user.version,
    }


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object.")
    return body


def _uuid(value: object, field: str, *, optional: bool = False) -> uuid.UUID | None:
    if optional and value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise validation_error({field: "Must be a valid UUID."}) from error


def _role(value: object) -> UserRole:
    try:
        return UserRole(str(value))
    except ValueError as error:
        raise validation_error({"role": "Must be OPERATOR or VIEWER."}) from error


def _status(value: str | None) -> UserStatus | None:
    if value is None or value == "":
        return None
    try:
        return UserStatus(value)
    except ValueError as error:
        raise validation_error({"status": "Unknown user status."}) from error


def _limit(value: str | None) -> int:
    if value is None or value == "":
        return 20
    try:
        return int(value)
    except ValueError as error:
        raise validation_error({"limit": "Must be an integer."}) from error


def _handle_service_error(error: Exception) -> ApiError:
    if isinstance(error, UserNotFoundError):
        return ApiError(404, "user_not_found", "User was not found.")
    if isinstance(error, UserRequestError):
        details = {"field_errors": {error.field: error.message}} if error.field else None
        return ApiError(422, error.code, error.message, details=details)
    if isinstance(error, UserConflictError):
        status = 403 if error.code == "forbidden" else 409
        return ApiError(status, error.code, error.message)
    raise error


@areas_blueprint.get("/areas")
@require_auth(UserRole.ADMIN, UserRole.OPERATOR)
def list_areas():  # type: ignore[no-untyped-def]
    items = [
        {"id": str(area.id), "code": area.code, "name": area.name}
        for area in user_service().list_areas()
    ]
    return jsonify({"items": items})


@admin_users_blueprint.get("")
@require_auth(UserRole.ADMIN)
def list_users():  # type: ignore[no-untyped-def]
    role_value = request.args.get("role")
    try:
        role = UserRole(role_value) if role_value else None
    except ValueError as error:
        raise validation_error({"role": "Unknown user role."}) from error
    try:
        page = user_service().list_users(
            UserListQuery(
                role=role,
                status=_status(request.args.get("status")),
                query=request.args.get("q"),
                limit=_limit(request.args.get("limit")),
                cursor=request.args.get("cursor"),
            )
        )
    except (UserRequestError, UserConflictError, UserNotFoundError) as error:
        raise _handle_service_error(error) from error
    return jsonify(
        {"items": [serialize_user(item) for item in page.items], "next_cursor": page.next_cursor}
    )


@admin_users_blueprint.post("")
@require_auth(UserRole.ADMIN)
def create_user():  # type: ignore[no-untyped-def]
    body = _json_body()
    field_errors: dict[str, str] = {}
    for field in ("username", "display_name", "password", "role"):
        if field not in body:
            field_errors[field] = "This field is required."
    if field_errors:
        raise validation_error(field_errors)
    try:
        user = user_service().create_user(
            actor_id=current_actor().id,
            username=body["username"],
            display_name=body["display_name"],
            password=body["password"],
            role=_role(body["role"]),
            area_id=_uuid(body.get("area_id"), "area_id", optional=True),
        )
    except (UserRequestError, UserConflictError, UserNotFoundError) as error:
        raise _handle_service_error(error) from error
    return jsonify(serialize_user(user)), 201


@admin_users_blueprint.get("/<user_id>")
@require_auth(UserRole.ADMIN)
def get_user(user_id: str):  # type: ignore[no-untyped-def]
    parsed = _uuid(user_id, "id")
    assert parsed is not None
    try:
        user = user_service().get_user(parsed)
    except (UserRequestError, UserConflictError, UserNotFoundError) as error:
        raise _handle_service_error(error) from error
    return jsonify(serialize_user(user))


@admin_users_blueprint.patch("/<user_id>")
@require_auth(UserRole.ADMIN)
def update_user(user_id: str):  # type: ignore[no-untyped-def]
    parsed = _uuid(user_id, "id")
    assert parsed is not None
    body = _json_body()
    field_errors: dict[str, str] = {}
    for field in ("display_name", "role", "version"):
        if field not in body:
            field_errors[field] = "This field is required."
    if not isinstance(body.get("version"), int) or isinstance(body.get("version"), bool):
        field_errors["version"] = "Must be an integer."
    if (
        "password" in body
        and body["password"] is not None
        and not isinstance(body["password"], str)
    ):
        field_errors["password"] = "Must be a string."
    if field_errors:
        raise validation_error(field_errors)
    try:
        user = user_service().update_user(
            parsed,
            actor_id=current_actor().id,
            display_name=body["display_name"],
            role=_role(body["role"]),
            area_id=_uuid(body.get("area_id"), "area_id", optional=True),
            password=body.get("password"),
            version=body["version"],
        )
    except (UserRequestError, UserConflictError, UserNotFoundError) as error:
        raise _handle_service_error(error) from error
    return jsonify(serialize_user(user))


def _change_status(user_id: str, action: str):  # type: ignore[no-untyped-def]
    parsed = _uuid(user_id, "id")
    assert parsed is not None
    try:
        user = user_service().change_status(parsed, actor_id=current_actor().id, action=action)
    except (UserRequestError, UserConflictError, UserNotFoundError) as error:
        raise _handle_service_error(error) from error
    return jsonify(serialize_user(user))


@admin_users_blueprint.post("/<user_id>/lock")
@require_auth(UserRole.ADMIN)
def lock_user(user_id: str):  # type: ignore[no-untyped-def]
    return _change_status(user_id, "lock")


@admin_users_blueprint.post("/<user_id>/unlock")
@require_auth(UserRole.ADMIN)
def unlock_user(user_id: str):  # type: ignore[no-untyped-def]
    return _change_status(user_id, "unlock")


@admin_users_blueprint.post("/<user_id>/deactivate")
@require_auth(UserRole.ADMIN)
def deactivate_user(user_id: str):  # type: ignore[no-untyped-def]
    return _change_status(user_id, "deactivate")
