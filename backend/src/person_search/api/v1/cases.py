from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from typing import Any, cast

from flask import Blueprint, Response, current_app, jsonify, request

from person_search.api.errors import ApiError, validation_error
from person_search.auth.web import current_actor, require_auth
from person_search.services.cases import (
    UNSET,
    CaseAccessDeniedError,
    CaseClosedError,
    CaseDetail,
    CaseListQuery,
    CaseNotFoundError,
    CaseResultView,
    CaseService,
    CaseSummary,
    InvalidCaseRequestError,
    TrackNotSavableError,
)
from person_search.services.track_imagery import (
    ImageAccessDeniedError,
    ImageVariant,
    TrackImageNotFoundError,
    TrackImageUnavailableError,
    parse_crop_aspect,
    parse_crop_mark,
)
from person_search.storage.postgres.errors import ConcurrentUpdateError
from person_search.storage.postgres.models import CaseStatus, UserRole

cases_blueprint = Blueprint("cases", __name__, url_prefix="/cases")

READERS = (UserRole.OPERATOR, UserRole.VIEWER)
PATCH_FIELDS = frozenset({"title", "note", "status", "version"})
CREATE_FIELDS = frozenset({"title", "note", "track_id"})


def case_service() -> CaseService:
    return cast(
        CaseService, current_app.extensions["person_search.dependencies"].get("cases.service")
    )


def image_service():
    return current_app.extensions["person_search.dependencies"].get("track_images.service")


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_case(case: CaseSummary) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "title": case.title,
        "note": case.note,
        "owner": {
            "id": str(case.owner_user_id),
            "display_name": case.owner_display_name,
            "status": case.owner_status.value,
        },
        "result_count": case.result_count,
        "created_at": _iso(case.created_at),
        "updated_at": _iso(case.updated_at),
        "version": case.version,
        "status": case.status.value,
        "closed_at": _iso(case.closed_at) if case.closed_at else None,
    }


def serialize_result(result: CaseResultView) -> dict[str, Any]:
    base = f"/api/v1/cases/{result.case_id}/results/{result.id}"
    box = result.bbox
    return {
        "id": str(result.id),
        "case_id": str(result.case_id),
        "track_id": str(result.track_id),
        "camera_name": result.camera_name,
        "area_name": result.area_name,
        "appeared_at": _iso(result.appeared_at),
        "saved_at": _iso(result.saved_at),
        "bbox": (
            {
                "x": box.x,
                "y": box.y,
                "width": box.width,
                "height": box.height,
                "frame_width": box.frame_width,
                "frame_height": box.frame_height,
            }
            if box
            else None
        ),
        "crop_url": f"{base}/crop",
        "frame_url": f"{base}/frame",
    }


def serialize_detail(detail: CaseDetail) -> dict[str, Any]:
    return {
        "case": serialize_case(detail.case),
        "results": [serialize_result(item) for item in detail.results],
    }


def _json_body() -> dict[str, Any]:
    if not request.is_json:
        raise ApiError(415, "json_required", "Yêu cầu phải dùng JSON.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_json", "Nội dung JSON không hợp lệ.")
    return body


def _reject_unknown(body: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise validation_error({field: "Không được phép thay đổi trường này." for field in unknown})


def _uuid(value: object, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise validation_error({field: "Phải là UUID hợp lệ."}) from error


def _optional_text(body: dict[str, Any], field: str) -> str | None:
    value = body.get(field)
    if value is not None and not isinstance(value, str):
        raise validation_error({field: "Phải là chuỗi."})
    return value


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


def _status(value: object, field: str = "status") -> CaseStatus:
    try:
        return CaseStatus(value)
    except ValueError as error:
        raise validation_error({field: "Phải là OPEN hoặc CLOSED."}) from error


def _limit(value: str | None) -> int:
    if value is None or value == "":
        return 20
    try:
        return int(value)
    except ValueError as error:
        raise validation_error({"limit": "Phải là số nguyên."}) from error


def _service_error(error: Exception) -> ApiError:
    if isinstance(error, CaseNotFoundError):
        return ApiError(404, "case_not_found", "Không tìm thấy vụ việc.")
    if isinstance(error, CaseClosedError):
        return ApiError(
            409, "case_closed", "Vụ việc đã hoàn thành. Mở lại vụ việc trước khi chỉnh sửa."
        )
    if isinstance(error, TrackNotSavableError):
        return ApiError(
            403, "track_not_savable", "Kết quả này không thuộc khu vực hiện tại của bạn."
        )
    if isinstance(error, CaseAccessDeniedError):
        return ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.")
    if isinstance(error, ConcurrentUpdateError):
        return ApiError(
            409, "version_conflict", "Vụ việc đã được thay đổi ở nơi khác. Vui lòng tải lại."
        )
    if isinstance(error, InvalidCaseRequestError):
        return ApiError(422, "validation_failed", str(error))
    raise error


SERVICE_ERRORS = (
    CaseNotFoundError,
    CaseClosedError,
    TrackNotSavableError,
    CaseAccessDeniedError,
    ConcurrentUpdateError,
    InvalidCaseRequestError,
)


@cases_blueprint.get("")
@require_auth(*READERS)
def list_cases():  # type: ignore[no-untyped-def]
    raw_owner = request.args.get("owner_user_id")
    created_from = _date_time(request.args.get("created_from"), "created_from", end=False)
    created_to = _date_time(request.args.get("created_to"), "created_to", end=True)
    if created_from and created_to and created_from > created_to:
        raise validation_error({"created_to": "Phải sau thời điểm bắt đầu."})
    query = CaseListQuery(
        owner_user_id=_uuid(raw_owner, "owner_user_id") if raw_owner else None,
        created_from=created_from,
        created_to=created_to,
        limit=_limit(request.args.get("limit")),
        cursor=request.args.get("cursor") or None,
        status=_status(request.args["status"]) if request.args.get("status") else None,
    )
    try:
        page = case_service().list_cases(current_actor().id, query)
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return jsonify(
        {"items": [serialize_case(item) for item in page.items], "next_cursor": page.next_cursor}
    )


@cases_blueprint.post("")
@require_auth(UserRole.OPERATOR)
def create_case():  # type: ignore[no-untyped-def]
    body = _json_body()
    _reject_unknown(body, CREATE_FIELDS)
    title = body.get("title")
    if not isinstance(title, str):
        raise validation_error({"title": "Không được để trống."})
    track_id = body.get("track_id")
    try:
        detail = case_service().create_case(
            current_actor().id,
            title=title,
            note=_optional_text(body, "note"),
            track_id=_uuid(track_id, "track_id") if track_id is not None else None,
        )
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return jsonify(serialize_detail(detail)), 201


@cases_blueprint.get("/<uuid:case_id>")
@require_auth(*READERS)
def get_case(case_id: uuid.UUID):  # type: ignore[no-untyped-def]
    try:
        detail = case_service().get_case(current_actor().id, case_id)
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return jsonify(serialize_detail(detail))


@cases_blueprint.patch("/<uuid:case_id>")
@require_auth(UserRole.OPERATOR)
def update_case(case_id: uuid.UUID):  # type: ignore[no-untyped-def]
    body = _json_body()
    _reject_unknown(body, PATCH_FIELDS)
    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise validation_error({"version": "Bắt buộc và phải là số nguyên."})
    title = body["title"] if "title" in body else UNSET
    if title is not UNSET and not isinstance(title, str):
        raise validation_error({"title": "Không được để trống."})
    note = _optional_text(body, "note") if "note" in body else UNSET
    status = _status(body["status"]) if "status" in body else UNSET
    try:
        summary = case_service().update_case(
            current_actor().id,
            case_id,
            title=title,
            note=note,
            status=status,
            expected_version=version,
        )
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return jsonify(serialize_case(summary))


@cases_blueprint.post("/<uuid:case_id>/results")
@require_auth(UserRole.OPERATOR)
def add_result(case_id: uuid.UUID):  # type: ignore[no-untyped-def]
    body = _json_body()
    _reject_unknown(body, frozenset({"track_id"}))
    track_id = _uuid(body.get("track_id"), "track_id")
    try:
        result = case_service().add_result(current_actor().id, case_id, track_id)
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return jsonify(serialize_result(result)), 201


@cases_blueprint.delete("/<uuid:case_id>/results/<uuid:case_result_id>")
@require_auth(UserRole.OPERATOR)
def remove_result(case_id: uuid.UUID, case_result_id: uuid.UUID):  # type: ignore[no-untyped-def]
    try:
        case_service().remove_result(current_actor().id, case_id, case_result_id)
    except SERVICE_ERRORS as error:
        raise _service_error(error) from error
    return Response(status=204)


@cases_blueprint.get("/<uuid:case_id>/results/<uuid:case_result_id>/crop")
@require_auth(*READERS)
def result_crop(case_id: uuid.UUID, case_result_id: uuid.UUID):  # type: ignore[no-untyped-def]
    try:
        aspect = parse_crop_aspect(request.args.get("aspect"))
    except ValueError as error:
        raise ApiError(422, "invalid_aspect", str(error)) from error
    try:
        mark = parse_crop_mark(request.args.get("mark"))
    except ValueError as error:
        raise ApiError(422, "invalid_mark", str(error)) from error
    return _case_image(case_id, case_result_id, ImageVariant.PERSON_CROP, aspect, mark)


@cases_blueprint.get("/<uuid:case_id>/results/<uuid:case_result_id>/frame")
@require_auth(*READERS)
def result_frame(case_id: uuid.UUID, case_result_id: uuid.UUID):  # type: ignore[no-untyped-def]
    return _case_image(case_id, case_result_id, ImageVariant.FULL_FRAME)


def _case_image(
    case_id: uuid.UUID,
    case_result_id: uuid.UUID,
    variant: ImageVariant,
    aspect: float | None = None,
    mark: bool = False,
):
    try:
        image = image_service().case_result_image(
            current_actor().id,
            case_result_id,
            variant,
            case_id=case_id,
            aspect=aspect,
            mark=mark,
        )
    except ImageAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền xem ảnh này.") from error
    except TrackImageNotFoundError as error:
        raise ApiError(
            404, "case_result_not_found", "Không tìm thấy kết quả trong vụ việc."
        ) from error
    except TrackImageUnavailableError as error:
        raise ApiError(
            410,
            "image_unavailable",
            "Ảnh track không còn khả dụng.",
            details={"reason": error.reason},
        ) from error
    return Response(
        image.content,
        mimetype=image.media_type,
        headers={"Cache-Control": image.cache_control, "X-Content-Type-Options": "nosniff"},
    )
