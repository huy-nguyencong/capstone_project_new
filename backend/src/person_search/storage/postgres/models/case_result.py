"""Saved immutable snapshot of a search result."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base


class CaseResult(Base):
    __tablename__ = "case_results"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(camera_name_snapshot)) > 0",
            name="ck_case_results_camera_name_not_blank",
        ),
        CheckConstraint(
            "length(btrim(area_name_snapshot)) > 0",
            name="ck_case_results_area_name_not_blank",
        ),
        Index("ix_case_results_case_saved_at", "case_id", "saved_at"),
        Index("ix_case_results_track_id", "track_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person_tracks.id", ondelete="RESTRICT"), nullable=False
    )
    camera_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    area_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    appeared_at_snapshot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
