from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base

WORKER_RUN_STATES = ("STARTING", "IDLE", "BUSY", "STOPPING", "STOPPED")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (
        CheckConstraint(
            "state IN ('STARTING', 'IDLE', 'BUSY', 'STOPPING', 'STOPPED')",
            name="ck_worker_heartbeats_state",
        ),
        CheckConstraint(
            "heartbeat_at >= started_at", name="ck_worker_heartbeats_heartbeat_after_start"
        ),
        CheckConstraint(
            "(rss_bytes IS NULL OR rss_bytes >= 0) AND (cpu_percent IS NULL OR cpu_percent >= 0)",
            name="ck_worker_heartbeats_resources_nonnegative",
        ),
        Index("ix_worker_heartbeats_heartbeat_at", "heartbeat_at"),
    )

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rss_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
