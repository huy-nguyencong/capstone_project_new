"""Versioned AI pipeline configuration."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Enum, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.enums import AIConfigStatus


class AIConfigVersion(TimestampMixin, Base):
    __tablename__ = "ai_config_versions"
    __table_args__ = (
        CheckConstraint("encoder_dimension > 0", name="ck_ai_config_encoder_dimension_positive"),
        CheckConstraint(
            "checkpoint_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_config_checkpoint_sha256"
        ),
        Index(
            "uq_ai_config_single_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(100), nullable=False)
    tracker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tracker_version: Mapped[str] = mapped_column(String(100), nullable=False)
    encoder_name: Mapped[str] = mapped_column(String(100), nullable=False)
    encoder_version: Mapped[str] = mapped_column(String(100), nullable=False)
    encoder_dimension: Mapped[int] = mapped_column(nullable=False)
    checkpoint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AIConfigStatus] = mapped_column(
        Enum(AIConfigStatus, name="ai_config_status", native_enum=True),
        nullable=False,
        default=AIConfigStatus.DRAFT,
        server_default=AIConfigStatus.DRAFT.value,
    )
