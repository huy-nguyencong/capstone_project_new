"""PersonTrack metadata and cross-storage readiness state."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    event,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.enums import TrackIndexStatus


class TrackStateTransitionError(ValueError):
    """Raised before flush for an invalid track state transition."""


ALLOWED_TRACK_TRANSITIONS = {
    TrackIndexStatus.PENDING: {
        TrackIndexStatus.PENDING,
        TrackIndexStatus.READY,
        TrackIndexStatus.FAILED,
    },
    TrackIndexStatus.FAILED: {TrackIndexStatus.FAILED, TrackIndexStatus.PENDING},
    TrackIndexStatus.READY: {TrackIndexStatus.READY},
}


class PersonTrack(TimestampMixin, Base):
    __tablename__ = "person_tracks"
    __table_args__ = (
        CheckConstraint("source_started_at_ms >= 0", name="ck_tracks_source_start_nonnegative"),
        CheckConstraint(
            "source_ended_at_ms >= source_started_at_ms", name="ck_tracks_source_end_order"
        ),
        CheckConstraint(
            "representative_frame_timestamp_ms BETWEEN source_started_at_ms AND source_ended_at_ms",
            name="ck_tracks_representative_timestamp_range",
        ),
        CheckConstraint("bbox_x >= 0 AND bbox_y >= 0", name="ck_tracks_bbox_origin"),
        CheckConstraint("bbox_width > 0 AND bbox_height > 0", name="ck_tracks_bbox_size"),
        CheckConstraint("frame_width > 0 AND frame_height > 0", name="ck_tracks_frame_size"),
        CheckConstraint(
            "bbox_x + bbox_width <= frame_width AND bbox_y + bbox_height <= frame_height",
            name="ck_tracks_bbox_within_frame",
        ),
        CheckConstraint(
            "frame_sha256 IS NULL OR frame_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_tracks_frame_sha256",
        ),
        CheckConstraint(
            "index_status <> 'READY' OR (minio_object_key IS NOT NULL AND "
            "frame_sha256 IS NOT NULL AND frame_size_bytes > 0 AND vector_indexed_at IS NOT NULL)",
            name="ck_tracks_ready_artifacts",
        ),
        Index("ix_person_tracks_camera_appeared_at", "camera_id", "appeared_at_utc"),
        Index("ix_person_tracks_index_status", "index_status"),
        Index(
            "ix_person_tracks_ready_camera_appeared_at",
            "camera_id",
            "appeared_at_utc",
            postgresql_where=text("index_status = 'READY'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ai_config_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_config_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appeared_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_frame_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_started_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ended_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    representative_frame_timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bbox_x: Mapped[int] = mapped_column(nullable=False)
    bbox_y: Mapped[int] = mapped_column(nullable=False)
    bbox_width: Mapped[int] = mapped_column(nullable=False)
    bbox_height: Mapped[int] = mapped_column(nullable=False)
    frame_width: Mapped[int] = mapped_column(nullable=False)
    frame_height: Mapped[int] = mapped_column(nullable=False)
    minio_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    frame_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frame_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    encoder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    vector_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    index_status: Mapped[TrackIndexStatus] = mapped_column(
        Enum(TrackIndexStatus, name="track_index_status", native_enum=True),
        nullable=False,
        default=TrackIndexStatus.PENDING,
        server_default=TrackIndexStatus.PENDING.value,
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)


@event.listens_for(PersonTrack, "before_update")
def reject_invalid_track_transition(mapper, connection, target: PersonTrack) -> None:  # type: ignore[no-untyped-def]
    history = inspect(target).attrs.index_status.history
    if not history.has_changes() or not history.deleted or not history.added:
        return
    previous = history.deleted[0]
    requested = history.added[0]
    if requested not in ALLOWED_TRACK_TRANSITIONS[previous]:
        raise TrackStateTransitionError(
            f"Invalid PersonTrack transition: {previous} -> {requested}."
        )
