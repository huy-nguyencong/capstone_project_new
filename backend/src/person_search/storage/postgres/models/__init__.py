"""PostgreSQL model registry."""

from person_search.storage.postgres.models.ai_config import AIConfigVersion
from person_search.storage.postgres.models.area import Area
from person_search.storage.postgres.models.base import Base
from person_search.storage.postgres.models.camera import Camera
from person_search.storage.postgres.models.enums import (
    AIConfigStatus,
    CameraStatus,
    JobSourceType,
    JobStatus,
    OutboxStatus,
    RtspStatus,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.models.guards import ImmutableFieldError
from person_search.storage.postgres.models.outbox import StorageOutboxEvent
from person_search.storage.postgres.models.person_track import (
    PersonTrack,
    TrackStateTransitionError,
)
from person_search.storage.postgres.models.processing_job import ProcessingJob
from person_search.storage.postgres.models.user import User

__all__ = [
    "AIConfigStatus",
    "AIConfigVersion",
    "Area",
    "Base",
    "Camera",
    "CameraStatus",
    "ImmutableFieldError",
    "JobSourceType",
    "JobStatus",
    "OutboxStatus",
    "PersonTrack",
    "ProcessingJob",
    "RtspStatus",
    "StorageOutboxEvent",
    "TrackIndexStatus",
    "TrackStateTransitionError",
    "User",
    "UserRole",
    "UserStatus",
]
