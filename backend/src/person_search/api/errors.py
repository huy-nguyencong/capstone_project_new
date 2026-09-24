"""Minimal JSON error handling to be finalized in BE-01."""

from __future__ import annotations

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


def register_error_handlers(app: Flask) -> None:
    """Return JSON for HTTP failures under API and health namespaces."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):  # type: ignore[no-untyped-def]
        if not (request.path.startswith("/api/") or request.path.startswith("/health/")):
            return error

        response = jsonify(
            {
                "error": {
                    "code": error.name.lower().replace(" ", "_"),
                    "message": error.description,
                }
            }
        )
        response.status_code = error.code or 500
        return response
