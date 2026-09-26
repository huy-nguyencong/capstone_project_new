from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from person_search.api.errors import ApiError, validation_error
from person_search.api.rate_limit import rate_limited
from person_search.auth.web import current_actor, require_auth
from person_search.services.audit import (
    AuditAccessDeniedError,
    AuditEvent,
    AuditLogQuery,
    AuditLogView,
    InvalidAuditQueryError,
)
from person_search.services.monitoring import iso
from person_search.storage.postgres.models import AuditResult, UserRole

monitor_blueprint = Blueprint("monitor", __name__, url_prefix="/admin")


def _service(name: str) -> Any:
    return current_app.extensions["person_search.dependencies"].get(name)


def _date_time(value: str | None, field: str, *, end: bool) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        if len(value) == 10:
            day = datetime.fromisoformat(value).date()
            return datetime.combine(day, time.max if end else time.min, tzinfo=UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except ValueError as error:
        raise validation_error({field: "Thời gian phải theo định dạng ISO 8601."}) from error


def _audit_item(item: AuditLogView) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "occurred_at": iso(item.occurred_at),
        "actor": (
            {"id": str(item.actor_user_id), "username": item.actor_username}
            if item.actor_user_id is not None
            else None
        ),
        "event_type": item.event_type,
        "target_type": item.target_type,
        "target_id": str(item.target_id) if item.target_id else None,
        "target_label": item.target_label,
        "result": item.result.value,
        "metadata": item.metadata,
    }


@monitor_blueprint.get("/system-status")
@require_auth(UserRole.ADMIN)
def system_status():  # type: ignore[no-untyped-def]
    return jsonify(_service("monitoring.service").system_status())


@monitor_blueprint.post("/diagnostics/camera-pipeline")
@require_auth(UserRole.ADMIN)
@rate_limited("diagnostics")
def camera_pipeline():  # type: ignore[no-untyped-def]
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) != {"camera_id"}:
        raise validation_error({"camera_id": "Bắt buộc."})
    try:
        camera_id = uuid.UUID(str(body["camera_id"]))
    except ValueError as error:
        raise validation_error({"camera_id": "Phải là UUID hợp lệ."}) from error
    return jsonify(
        _service("monitoring.service").camera_pipeline(camera_id, actor_id=current_actor().id)
    )


@monitor_blueprint.post("/diagnostics/search-components")
@require_auth(UserRole.ADMIN)
@rate_limited("diagnostics")
def search_components():  # type: ignore[no-untyped-def]
    return jsonify(
        _service("monitoring.service").search_components(actor_id=current_actor().id)
    )


@monitor_blueprint.get("/audit-logs")
@require_auth(UserRole.ADMIN)
def audit_logs():  # type: ignore[no-untyped-def]
    args = request.args
    try:
        event_types = tuple(AuditEvent(value) for value in args.getlist("event_type"))
    except ValueError as error:
        raise validation_error({"event_type": "Loại sự kiện không hợp lệ."}) from error
    try:
        result = AuditResult(args["result"]) if args.get("result") else None
    except ValueError as error:
        raise validation_error({"result": "Phải là SUCCESS hoặc FAILURE."}) from error
    try:
        actor_id = uuid.UUID(args["actor_user_id"]) if args.get("actor_user_id") else None
    except ValueError as error:
        raise validation_error({"actor_user_id": "Phải là UUID hợp lệ."}) from error
    try:
        limit = int(args.get("limit") or 50)
    except ValueError as error:
        raise validation_error({"limit": "Phải là số nguyên."}) from error
    query = AuditLogQuery(
        occurred_from=_date_time(args.get("occurred_from"), "occurred_from", end=False),
        occurred_to=_date_time(args.get("occurred_to"), "occurred_to", end=True),
        actor_user_id=actor_id,
        event_types=event_types,
        result=result,
        limit=limit,
        cursor=args.get("cursor") or None,
    )
    try:
        page = _service("audit.service").list(current_actor().id, query)
    except InvalidAuditQueryError as error:
        raise ApiError(422, "validation_failed", str(error)) from error
    except AuditAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.") from error
    return jsonify(
        {"items": [_audit_item(item) for item in page.items], "next_cursor": page.next_cursor}
    )


@monitor_blueprint.get("/audit-logs/actors")
@require_auth(UserRole.ADMIN)
def audit_actors():  # type: ignore[no-untyped-def]
    try:
        actors = _service("audit.service").actors(current_actor().id)
    except AuditAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.") from error
    return jsonify(
        {
            "items": [
                {
                    "id": str(actor.id),
                    "username": actor.username,
                    "display_name": actor.display_name,
                    "role": actor.role.value,
                }
                for actor in actors
            ]
        }
    )
