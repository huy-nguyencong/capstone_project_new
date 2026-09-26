from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from flask import Flask, Response, g, jsonify, request
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import HTTPException

from person_search.dependencies import DependencyNotConfiguredError
from person_search.observability import bind_context, reset_context

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def validation_error(field_errors: dict[str, str]) -> ApiError:
    return ApiError(
        422,
        "validation_failed",
        "Dữ liệu gửi lên không hợp lệ.",
        details={"field_errors": field_errors},
    )


def _is_api_request() -> bool:
    return request.path.startswith("/api/") or request.path.startswith("/health/")


def error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> tuple[Response, int]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    body["request_id"] = g.get("request_id")
    return jsonify({"error": body}), status


def register_error_handlers(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        g.request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else str(uuid.uuid4())
        g.log_context_token = bind_context(request_id=g.request_id)

    @app.teardown_request
    def release_log_context(error: BaseException | None) -> None:
        token = g.pop("log_context_token", None)
        if token is not None:
            try:
                reset_context(token)
            except ValueError:
                pass

    @app.after_request
    def expose_request_id(response: Response) -> Response:
        request_id = g.get("request_id")
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):  # type: ignore[no-untyped-def]
        return error_response(error.status, error.code, error.message, error.details)

    @app.errorhandler(413)
    def handle_upload_too_large(error):
        return error_response(413, "file_too_large", "Video vượt giới hạn dung lượng.")

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):  # type: ignore[no-untyped-def]
        if not _is_api_request():
            return error
        return error_response(
            error.code or 500,
            (error.name or "error").lower().replace(" ", "_"),
            error.description or "",
        )

    @app.errorhandler(DependencyNotConfiguredError)
    @app.errorhandler(OperationalError)
    def handle_unavailable(error: Exception):  # type: ignore[no-untyped-def]
        logger.error(
            "dependency unavailable",
            extra={"error_type": type(error).__name__, "request_id": g.get("request_id")},
        )
        return error_response(
            503, "service_unavailable", "Hệ thống tạm thời không khả dụng. Vui lòng thử lại sau."
        )

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):  # type: ignore[no-untyped-def]
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        if app.config.get("PROPAGATE_EXCEPTIONS"):
            raise error
        logger.exception("unhandled api error", extra={"request_id": g.get("request_id")})
        return error_response(500, "internal_error", "Đã xảy ra lỗi hệ thống.")
