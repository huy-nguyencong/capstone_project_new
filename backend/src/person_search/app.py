"""Flask application factory."""

from __future__ import annotations

import atexit
from collections.abc import Mapping
from typing import Any

from flask import Flask

from person_search.api import register_api
from person_search.auth.passwords import PasswordHasher
from person_search.config import (
    StorageSettings,
    config_for_environment,
    parse_boolean_environment,
)
from person_search.dependencies import DependencyContainer
from person_search.services.auth import AuthService, SessionPolicy
from person_search.services.users import UserService
from person_search.storage.health import StorageHealthService
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.storage.runtime import StorageRuntime


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    dependencies: DependencyContainer | None = None,
) -> Flask:
    """Create an isolated application instance without opening external connections."""

    app = Flask(__name__)
    requested_environment = None
    if config:
        requested_environment = config.get("ENVIRONMENT")
        if requested_environment is None and config.get("TESTING"):
            requested_environment = "testing"
    app.config.from_object(config_for_environment(requested_environment))
    app.config["AUTH_COOKIE_SECURE"] = parse_boolean_environment(
        "PERSON_SEARCH_COOKIE_SECURE", default=app.config["AUTH_COOKIE_SECURE"]
    )

    if config:
        app.config.from_mapping(config)

    container = dependencies or DependencyContainer()
    if dependencies is None:
        if app.config["STORAGE_ENABLED"]:
            settings = StorageSettings.from_environment()
            runtime = StorageRuntime.from_settings(settings)
            container.register("storage.settings", settings)
            container.register("storage.postgres", runtime.postgres)
            container.register("storage.milvus", runtime.milvus)
            container.register("storage.minio", runtime.minio)
            container.register("storage.health", runtime.health)
            session_factory = runtime.postgres.session_factory
            password_hasher = PasswordHasher()
            container.register(
                "auth.service",
                AuthService(
                    lambda: UnitOfWork(session_factory),
                    hasher=password_hasher,
                    policy=SessionPolicy.from_environment(),
                ),
            )
            container.register(
                "users.service",
                UserService(lambda: UnitOfWork(session_factory), hasher=password_hasher),
            )
            app.extensions["person_search.storage_runtime"] = runtime
            atexit.register(runtime.close)
        else:
            container.register("storage.health", StorageHealthService(()))

    app.extensions["person_search.dependencies"] = container
    register_api(app)

    return app
