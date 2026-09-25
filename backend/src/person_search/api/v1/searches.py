from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, time
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from person_search.api.errors import ApiError
from person_search.api.rate_limit import rate_limited
from person_search.auth.web import current_actor, require_auth
from person_search.services.searches import (
    EncoderUnavailableError,
    InvalidQueryImageError,
    SearchResponse,
)
from person_search.services.track_imagery import (
    ImageAccessDeniedError,
    ImageVariant,
    TrackImageNotFoundError,
    TrackImageUnavailableError,
)
from person_search.services.track_search import (
    CameraOutOfScopeError,
    InvalidSearchRequestError,
    SearchNotAllowedError,
)
from person_search.storage.postgres.models import UserRole

search_blueprint = Blueprint("searches", __name__)


def search_service():
    return current_app.extensions["person_search.dependencies"].get("searches.service")


def image_service():
    return current_app.extensions["person_search.dependencies"].get("track_images.service")


@search_blueprint.get("/me/cameras")
@require_auth(UserRole.OPERATOR)
def my_cameras():
    return jsonify(
        {
            "items": [
                {"id": str(c.id), "code": c.code, "name": c.name, "ai_enabled": c.ai_enabled}
                for c in search_service().cameras(current_actor().id)
            ]
        }
    )


@search_blueprint.post("/searches/image")
@require_auth(UserRole.OPERATOR)
@rate_limited("search")
def image_search():
    if set(request.files) != {"image"} or len(request.files.getlist("image")) != 1:
        raise ApiError(422, "invalid_image", "Vui lòng gửi đúng một ảnh JPEG hoặc PNG.")
    upload = request.files["image"]
    if upload.mimetype not in {"image/jpeg", "image/png"}:
        raise ApiError(422, "invalid_image", "Ảnh phải có định dạng JPEG hoặc PNG.")
    try:
        filters = _filters(request.form, multipart=True)
        content = upload.stream.read(10 * 1024 * 1024 + 1)
        response = _run(
            lambda: search_service().search_image(current_actor().id, content, **filters)
        )
    except InvalidQueryImageError as error:
        raise ApiError(422, "invalid_image", "Ảnh truy vấn không hợp lệ.") from error
    return jsonify(response)


@search_blueprint.post("/searches/text")
@require_auth(UserRole.OPERATOR)
@rate_limited("search")
def text_search():
    body = _json_body()
    text = body.pop("text", None)
    if not isinstance(text, str) or len(text.strip()) < 4 or len(text.strip()) > 1000:
        raise ApiError(422, "text_too_short", "Mô tả phải có từ 4 đến 1000 ký tự.")
    return jsonify(
        _run(
            lambda: search_service().search_text(current_actor().id, text.strip(), **_filters(body))
        )
    )


@search_blueprint.post("/searches/attributes")
@require_auth(UserRole.OPERATOR)
@rate_limited("search")
def attribute_search():
    body = _json_body()
    attributes = body.pop("attributes", None)
    if not isinstance(attributes, dict):
        raise ApiError(422, "invalid_attributes", "Thuộc tính tìm kiếm không hợp lệ.")
    try:
        return jsonify(
            _run(
                lambda: search_service().search_attributes(
                    current_actor().id, attributes, **_filters(body)
                )
            )
        )
    except ValueError as error:
        raise ApiError(422, "invalid_attributes", str(error)) from error


@search_blueprint.get("/search-results/<uuid:track_id>/crop")
@require_auth(UserRole.OPERATOR)
def result_crop(track_id: uuid.UUID):
    return _track_image(track_id, ImageVariant.PERSON_CROP)


@search_blueprint.get("/search-results/<uuid:track_id>/frame")
@require_auth(UserRole.OPERATOR)
def result_frame(track_id: uuid.UUID):
    return _track_image(track_id, ImageVariant.FULL_FRAME)


def _run(operation):
    try:
        return _response(operation())
    except CameraOutOfScopeError as error:
        raise ApiError(403, "camera_out_of_scope", "Camera nằm ngoài khu vực của bạn.") from error
    except (InvalidSearchRequestError, TypeError) as error:
        code = "invalid_top_k" if "top_k" in str(error) else "invalid_filters"
        raise ApiError(422, code, str(error)) from error
    except SearchNotAllowedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền tìm kiếm.") from error
    except EncoderUnavailableError as error:
        raise ApiError(503, "encoder_unavailable", "Bộ mã hóa tạm thời không khả dụng.") from error
    except (InvalidQueryImageError, ValueError):
        raise
    except ApiError:
        raise
    except Exception as error:
        raise ApiError(
            503, "vector_search_unavailable", "Dịch vụ tìm kiếm vector tạm thời không khả dụng."
        ) from error


def _filters(values: Any, *, multipart: bool = False) -> dict[str, object]:
    allowed = {"top_k", "camera_ids", "appeared_from", "appeared_to"}
    if set(values) - allowed:
        raise ApiError(422, "invalid_filters", "Bộ lọc chứa trường không được hỗ trợ.")
    try:
        top_k = int(values.get("top_k", 8))
    except (TypeError, ValueError) as error:
        raise ApiError(422, "invalid_top_k", "top_k phải là 4, 8, 12 hoặc 16.") from error
    if top_k not in {4, 8, 12, 16}:
        raise ApiError(422, "invalid_top_k", "top_k phải là 4, 8, 12 hoặc 16.")
    raw_cameras = values.get("camera_ids", [])
    if multipart and isinstance(raw_cameras, str):
        try:
            raw_cameras = json.loads(raw_cameras)
        except json.JSONDecodeError as error:
            raise ApiError(422, "invalid_filters", "camera_ids không hợp lệ.") from error
    if not isinstance(raw_cameras, list):
        raise ApiError(422, "invalid_filters", "camera_ids phải là một mảng.")
    try:
        camera_ids = tuple(uuid.UUID(value) for value in raw_cameras)
    except (ValueError, TypeError, AttributeError) as error:
        raise ApiError(422, "invalid_filters", "camera_ids không hợp lệ.") from error
    appeared_from = _date_time(values.get("appeared_from"), end=False)
    appeared_to = _date_time(values.get("appeared_to"), end=True)
    if appeared_from and appeared_to and appeared_from > appeared_to:
        raise ApiError(422, "invalid_filters", "Khoảng thời gian không hợp lệ.")
    return {
        "top_k": top_k,
        "camera_ids": camera_ids,
        "appeared_from": appeared_from,
        "appeared_to": appeared_to,
    }


def _date_time(value: object, *, end: bool) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ApiError(422, "invalid_filters", "Thời gian không hợp lệ.")
    try:
        if len(value) == 10:
            day = datetime.fromisoformat(value).date()
            return datetime.combine(day, time.max if end else time.min, tzinfo=UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except ValueError as error:
        raise ApiError(422, "invalid_filters", "Thời gian phải theo định dạng ISO 8601.") from error


def _json_body() -> dict[str, Any]:
    if not request.is_json:
        raise ApiError(415, "json_required", "Yêu cầu phải dùng JSON.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(422, "invalid_json", "Nội dung JSON không hợp lệ.")
    return dict(body)


def _response(value: SearchResponse) -> dict[str, object]:
    return {
        "mode": value.mode,
        "prompt": value.prompt,
        "encoder_version": value.encoder_version,
        "top_k": value.top_k,
        "results": [
            {
                "track_id": str(r.track_id),
                "matching_score": r.matching_score,
                "camera": {"id": str(r.camera_id), "name": r.camera_name},
                "area": {"id": str(r.area_id), "name": r.area_name},
                "appeared_at": r.appeared_at_utc.isoformat().replace("+00:00", "Z"),
                "bbox": {
                    "x": r.bbox.x,
                    "y": r.bbox.y,
                    "width": r.bbox.width,
                    "height": r.bbox.height,
                    "frame_width": r.bbox.frame_width,
                    "frame_height": r.bbox.frame_height,
                },
                "crop_url": f"/api/v1/search-results/{r.track_id}/crop",
                "frame_url": f"/api/v1/search-results/{r.track_id}/frame",
            }
            for r in value.results
        ],
    }


def _track_image(track_id: uuid.UUID, variant: ImageVariant):
    try:
        image = image_service().search_result_image(current_actor().id, track_id, variant)
    except ImageAccessDeniedError as error:
        raise ApiError(403, "forbidden", "Bạn không có quyền xem ảnh này.") from error
    except TrackImageNotFoundError as error:
        raise ApiError(404, "track_not_found", "Không tìm thấy ảnh track.") from error
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
