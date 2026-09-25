"""Add query-driven indexes for the finalized relational schema.

Revision ID: 20260925_0004
Revises: 20260925_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0004"
down_revision: str | None = "20260925_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_cameras_active_area",
        "cameras",
        ["area_id"],
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index(
        "ix_person_tracks_camera_appeared_at",
        "person_tracks",
        ["camera_id", "appeared_at_utc"],
    )
    op.create_index("ix_person_tracks_index_status", "person_tracks", ["index_status"])
    op.create_index(
        "ix_person_tracks_ready_camera_appeared_at",
        "person_tracks",
        ["camera_id", "appeared_at_utc"],
        postgresql_where=sa.text("index_status = 'READY'"),
    )


def downgrade() -> None:
    op.drop_index("ix_person_tracks_ready_camera_appeared_at", table_name="person_tracks")
    op.drop_index("ix_person_tracks_index_status", table_name="person_tracks")
    op.drop_index("ix_person_tracks_camera_appeared_at", table_name="person_tracks")
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_cameras_active_area", table_name="cameras")
