"""API blueprint registration."""

from flask import Flask

from person_search.api.errors import register_error_handlers
from person_search.api.health import health_blueprint
from person_search.api.rate_limit import FixedWindowLimiter
from person_search.api.security import register_security
from person_search.api.v1 import api_v1_blueprint
from person_search.auth.web import clear_rejected_session_cookie


def register_api(app: Flask) -> None:
    """Attach health and versioned API routes to an application instance."""

    app.register_blueprint(health_blueprint)
    app.register_blueprint(api_v1_blueprint, url_prefix="/api/v1")
    register_error_handlers(app)
    register_security(app)
    app.extensions.setdefault("person_search.rate_limiter", FixedWindowLimiter())
    app.after_request(clear_rejected_session_cookie)
