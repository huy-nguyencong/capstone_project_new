"""Camera model with immutable area ownership."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, event, inspect
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.enums import CameraStatus, RtspStatus
from person_search.storage.postgres.models.guards import ImmutableFieldError


class Camera(TimestampMixin, Base):
    __tablename__ = "cameras"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_cameras_code_uppercase"),
        CheckConstraint("length(btrim(code)) > 0", name="ck_cameras_code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_cameras_name_not_blank"),
        CheckConstraint(
            "rtsp_url IS NULL OR rtsp_url ~ '^rtsps?://'", name="ck_cameras_rtsp_scheme"
        ),
        CheckConstraint(
            "rtsp_url IS NULL OR rtsp_url !~ '^rtsps?://[^/]*@'",
            name="ck_cameras_rtsp_no_embedded_credentials",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rtsp_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    rtsp_secret_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[CameraStatus] = mapped_column(
        Enum(CameraStatus, name="camera_status", native_enum=True),
        nullable=False,
        default=CameraStatus.ACTIVE,
        server_default=CameraStatus.ACTIVE.value,
    )
    rtsp_status: Mapped[RtspStatus] = mapped_column(
        Enum(RtspStatus, name="rtsp_status", native_enum=True),
        nullable=False,
        default=RtspStatus.UNKNOWN,
        server_default=RtspStatus.UNKNOWN.value,
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


@event.listens_for(Camera, "before_update")
def reject_camera_area_change(mapper, connection, target: Camera) -> None:  # type: ignore[no-untyped-def]
    if inspect(target).attrs.area_id.history.has_changes():
        raise ImmutableFieldError("Camera.area_id is immutable after creation.")
