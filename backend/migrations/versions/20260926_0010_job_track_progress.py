"""Track completed and published worker progress separately.

Revision ID: 20260926_0010
Revises: 20260925_0009
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0010"
down_revision = "20260925_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processing_jobs",
        sa.Column("completed_tracks", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("published_tracks", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_jobs_track_progress",
        "processing_jobs",
        "completed_tracks >= 0 AND published_tracks >= 0 "
        "AND published_tracks <= completed_tracks",
    )


def downgrade():
    op.drop_constraint("ck_jobs_track_progress", "processing_jobs", type_="check")
    op.drop_column("processing_jobs", "published_tracks")
    op.drop_column("processing_jobs", "completed_tracks")
