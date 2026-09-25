"""Application user model and role-to-area invariant."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.enums import UserRole, UserStatus


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(btrim(username)) > 0", name="ck_users_username_not_blank"),
        CheckConstraint(
            "length(btrim(password_hash)) > 0", name="ck_users_password_hash_not_blank"
        ),
        CheckConstraint(
            "length(btrim(display_name)) > 0", name="ck_users_display_name_not_blank"
        ),
        CheckConstraint(
            "(role = 'OPERATOR' AND assigned_area_id IS NOT NULL) OR "
            "(role IN ('ADMIN', 'VIEWER') AND assigned_area_id IS NULL)",
            name="ck_users_role_assigned_area",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True), nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=True),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    assigned_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
