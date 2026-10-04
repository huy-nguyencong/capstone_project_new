"""Serve the built web application (``frontend/dist``) from the application server.

For the demonstration the Vite development server is not needed: the built files are static and
the browser then talks to the API on the same origin, so no proxy and no CORS configuration are
involved either. The directory is given by ``PERSON_SEARCH_STATIC_DIR`` (or the
``STATIC_FRONTEND_DIR`` setting); when it is not set, the server serves only the API and the health
checks.

Hashed build assets under ``assets/`` are served with a long cache lifetime; every other path that
is not an API or health path returns ``index.html`` so that the client-side router owns the URL.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, abort, send_from_directory
from werkzeug.security import safe_join

RESERVED_PREFIXES = ("api/", "health/")
# The global policy (``api/security.py``) is ``default-src 'none'`` for API responses; the page
# needs its own scripts and styles, fetches the API on the same origin and renders person images
# received as blobs.
PAGE_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
PAGE_CACHE_CONTROL = "no-cache"


def static_frontend_directory(app: Flask) -> Path | None:
    value = str(app.config.get("STATIC_FRONTEND_DIR") or "").strip()
    if not value:
        return None
    root = Path(value).resolve()
    if not (root / "index.html").is_file():
        raise RuntimeError(f"Static frontend directory has no index.html: {root}")
    return root


def register_static_frontend(app: Flask) -> bool:
    root = static_frontend_directory(app)
    if root is None:
        return False

    def _page(resource: str) -> Response:
        if resource.startswith(RESERVED_PREFIXES) or resource in ("api", "health"):
            abort(404)
        if resource:
            candidate = safe_join(str(root), resource)
            if candidate is not None and Path(candidate).is_file():
                response = send_from_directory(root, resource)
                if resource.startswith("assets/"):
                    response.headers["Cache-Control"] = ASSET_CACHE_CONTROL
                response.headers["Content-Security-Policy"] = PAGE_CONTENT_SECURITY_POLICY
                return response
        response = send_from_directory(root, "index.html")
        response.headers["Cache-Control"] = PAGE_CACHE_CONTROL
        response.headers["Content-Security-Policy"] = PAGE_CONTENT_SECURITY_POLICY
        return response

    app.add_url_rule("/", "static_frontend_index", lambda: _page(""), methods=["GET"])
    app.add_url_rule("/<path:resource>", "static_frontend_page", _page, methods=["GET"])
    app.extensions["person_search.static_frontend"] = root
    return True
