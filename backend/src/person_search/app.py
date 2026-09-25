"""Flask application factory."""

from __future__ import annotations

import atexit
import os
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
from person_search.services.audit import AuditLogService, AuditRecorder
from person_search.services.auth import AuthService, SessionPolicy
from person_search.services.camera_runtime import CameraRuntime
from person_search.services.cameras import CameraService
from person_search.services.cases import CaseService
from person_search.services.jobs import JobService
from person_search.services.monitoring import MonitoringService
from person_search.services.searches import SearchService
from person_search.services.track_imagery import TrackImageService
from person_search.services.users import UserService
from person_search.services.video_staging import VideoStaging
from person_search.storage.health import StorageHealthService
from person_search.storage.minio.frames import MinioFrameStore
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
    app.config["CORS_ORIGINS"] = tuple(
        origin.strip()
        for origin in os.getenv("PERSON_SEARCH_CORS_ORIGINS", "").split(",")
        if origin.strip()
    )

    if config:
        app.config.from_mapping(config)

    staging = VideoStaging.from_environment()
    app.config.setdefault("MAX_CONTENT_LENGTH", staging.max_bytes + 1024 * 1024)
    if app.config["MAX_CONTENT_LENGTH"] is None:
        app.config["MAX_CONTENT_LENGTH"] = staging.max_bytes + 1024 * 1024
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
            container.register(
                "jobs.service", JobService(lambda: UnitOfWork(session_factory), staging)
            )
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
            camera_runtime = CameraRuntime.from_environment()
            container.register(
                "cameras.service",
                CameraService(
                    lambda: UnitOfWork(session_factory),
                    camera_runtime,
                    CameraService.registry_from_environment(),
                ),
            )
            search_service = SearchService(
                lambda: UnitOfWork(session_factory), runtime.milvus.client
            )
            container.register("searches.service", search_service)
            container.register(
                "audit.service", AuditLogService(lambda: UnitOfWork(session_factory))
            )
            container.register(
                "monitoring.service",
                MonitoringService(
                    lambda: UnitOfWork(session_factory),
                    health=runtime.health,
                    search=search_service,
                    runtime=camera_runtime,
                ),
            )
            container.register(
                "cases.service",
                CaseService(
                    lambda: UnitOfWork(session_factory),
                    audit=AuditRecorder(lambda: UnitOfWork(session_factory)),
                ),
            )
            container.register(
                "track_images.service",
                TrackImageService(
                    lambda: UnitOfWork(session_factory),
                    MinioFrameStore(runtime.minio.client, settings.minio.bucket),
                ),
            )
            app.extensions["person_search.storage_runtime"] = runtime
            atexit.register(runtime.close)
        else:
            container.register("storage.health", StorageHealthService(()))

    app.extensions["person_search.dependencies"] = container
    register_api(app)

    return app
