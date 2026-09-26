"""Processing job source and progress metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.enums import JobSourceType, JobStatus


class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("sampling_interval > 0", name="ck_jobs_sampling_interval_positive"),
        CheckConstraint("processed_frames >= 0", name="ck_jobs_processed_frames_nonnegative"),
        CheckConstraint(
            "total_frames IS NULL OR total_frames >= processed_frames",
            name="ck_jobs_total_frames_progress",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_jobs_ended_after_started",
        ),
        CheckConstraint(
            "source_type <> 'FILE' OR source_ref IS NOT NULL", name="ck_jobs_file_source_ref"
        ),
        Index("ix_processing_jobs_status", "status"),
        Index("uq_jobs_actor_idempotency", "requested_by", "idempotency_key", unique=True),
        CheckConstraint("attempts >= 0 AND sampled_frames >= 0", name="ck_jobs_worker_counters"),
        CheckConstraint(
            "completed_tracks >= 0 AND published_tracks >= 0 "
            "AND published_tracks <= completed_tracks",
            name="ck_jobs_track_progress",
        ),
        CheckConstraint("jsonb_typeof(metrics) = 'object'", name="ck_jobs_metrics_object"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_digest: Mapped[str | None] = mapped_column(String(64))
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    sampled_frames: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    completed_tracks: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    published_tracks: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ai_config_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_config_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[JobSourceType] = mapped_column(
        Enum(JobSourceType, name="job_source_type", native_enum=True), nullable=False
    )
    source_ref: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=True),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
    )
    sampling_interval: Mapped[int] = mapped_column(nullable=False)
    timeline_origin_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_frames: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    total_frames: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    metrics_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
