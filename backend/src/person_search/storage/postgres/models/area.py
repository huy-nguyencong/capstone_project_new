"""Area model."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, String, event, inspect
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from person_search.storage.postgres.models.base import Base, TimestampMixin
from person_search.storage.postgres.models.guards import ImmutableFieldError


class Area(TimestampMixin, Base):
    __tablename__ = "areas"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_areas_code_uppercase"),
        CheckConstraint("length(btrim(code)) > 0", name="ck_areas_code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_areas_name_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


@event.listens_for(Area, "before_update")
def reject_area_code_change(mapper, connection, target: Area) -> None:  # type: ignore[no-untyped-def]
    if inspect(target).attrs.code.history.has_changes():
        raise ImmutableFieldError("Area.code is immutable after creation.")
