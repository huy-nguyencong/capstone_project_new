"""PostgreSQL model registry."""

from person_search.storage.postgres.models.area import Area
from person_search.storage.postgres.models.base import Base
from person_search.storage.postgres.models.camera import Camera
from person_search.storage.postgres.models.enums import (
    CameraStatus,
    RtspStatus,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.models.guards import ImmutableFieldError
from person_search.storage.postgres.models.user import User

__all__ = [
    "Area",
    "Base",
    "Camera",
    "CameraStatus",
    "ImmutableFieldError",
    "RtspStatus",
    "User",
    "UserRole",
    "UserStatus",
]
