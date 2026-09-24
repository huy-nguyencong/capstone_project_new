"""Flask application factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Flask

from person_search.api import register_api
from person_search.config import config_for_environment
from person_search.dependencies import DependencyContainer


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    dependencies: DependencyContainer | None = None,
) -> Flask:
    """Create an isolated application instance without opening external connections."""

    app = Flask(__name__)
    app.config.from_object(config_for_environment())

    if config:
        app.config.from_mapping(config)

    app.extensions["person_search.dependencies"] = dependencies or DependencyContainer()
    register_api(app)

    return app
