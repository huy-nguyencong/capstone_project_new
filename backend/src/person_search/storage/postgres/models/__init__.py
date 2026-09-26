"""PostgreSQL model registry."""

from person_search.storage.postgres.models.ai_config import AIConfigVersion
from person_search.storage.postgres.models.area import Area
from person_search.storage.postgres.models.audit_log import AuditLog
from person_search.storage.postgres.models.auth_session import AuthSession
from person_search.storage.postgres.models.base import Base
from person_search.storage.postgres.models.camera import Camera
from person_search.storage.postgres.models.case import Case
from person_search.storage.postgres.models.case_result import CaseResult
from person_search.storage.postgres.models.enums import (
    AIConfigStatus,
    AuditResult,
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
from person_search.storage.postgres.models.worker_heartbeat import WorkerHeartbeat

__all__ = [
    "AIConfigStatus",
    "AIConfigVersion",
    "Area",
    "AuditLog",
    "AuditResult",
    "AuthSession",
    "Base",
    "Camera",
    "CameraStatus",
    "Case",
    "CaseResult",
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
    "WorkerHeartbeat",
]
