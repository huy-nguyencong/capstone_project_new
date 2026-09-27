from __future__ import annotations

from flask import Blueprint, jsonify, request

from person_search.api.errors import ApiError, validation_error
from person_search.api.v1.cases import case_service, serialize_case
from person_search.auth.web import current_actor, require_auth
from person_search.services.cases import (
    MAX_RECENT_CASES,
    CaseAccessDeniedError,
    InvalidCaseRequestError,
)
from person_search.storage.postgres.models import UserRole

viewer_blueprint = Blueprint("viewer", __name__, url_prefix="/viewer")


def _recent_limit(value: str | None) -> int:
    if value is None or value == "":
        return 10
    try:
        return int(value)
    except ValueError as error:
        raise validation_error({"recent_limit": "Phải là số nguyên."}) from error


@viewer_blueprint.get("/dashboard")
@require_auth(UserRole.VIEWER)
def dashboard():  # type: ignore[no-untyped-def]
    try:
        value = case_service().viewer_dashboard(
            current_actor().id, recent_limit=_recent_limit(request.args.get("recent_limit"))
        )
    except InvalidCaseRequestError as error:
        raise validation_error({"recent_limit": f"Phải từ 1 đến {MAX_RECENT_CASES}."}) from error
    except CaseAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.") from error
    return jsonify(
        {
            "total_cases": value.total_cases,
            "total_case_results": value.total_case_results,
            "open_cases": value.open_cases,
            "closed_cases": value.closed_cases,
            "recent_cases": [serialize_case(item) for item in value.recent_cases],
        }
    )


@viewer_blueprint.get("/operators")
@require_auth(UserRole.VIEWER)
def operators():  # type: ignore[no-untyped-def]
    try:
        owners = case_service().viewer_operators(current_actor().id)
    except CaseAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.") from error
    return jsonify(
        {
            "items": [
                {
                    "id": str(owner.id),
                    "display_name": owner.display_name,
                    "status": owner.status.value,
                }
                for owner in owners
            ]
        }
    )
