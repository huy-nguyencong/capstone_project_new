from __future__ import annotations

from flask import Flask, Response, current_app, g, request

ALLOWED_HEADERS = "Content-Type, X-CSRF-Token, Idempotency-Key, X-Request-ID"
ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"


def _apply_cors(response: Response) -> None:
    origin = request.headers.get("Origin")
    if not origin:
        return
    response.vary.add("Origin")
    if origin not in current_app.config.get("CORS_ORIGINS", ()):
        return
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, Retry-After"
    if request.method == "OPTIONS":
        response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
        response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
        response.headers["Access-Control-Max-Age"] = "600"


def _apply_security_headers(response: Response) -> None:
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if request.path.startswith("/api/"):
        headers.setdefault("Cache-Control", "no-store")
    if current_app.config.get("AUTH_COOKIE_SECURE"):
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    retry_after = g.get("retry_after")
    if retry_after:
        headers["Retry-After"] = str(retry_after)


def register_security(app: Flask) -> None:
    @app.after_request
    def secure_response(response: Response) -> Response:
        _apply_cors(response)
        _apply_security_headers(response)
        return response
