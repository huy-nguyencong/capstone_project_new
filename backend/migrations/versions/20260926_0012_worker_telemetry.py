"""Worker heartbeat and bounded per-job runtime metrics.

Revision ID: 20260926_0012
Revises: 20260926_0011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_0012"
down_revision = "20260926_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processing_jobs",
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("metrics_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_jobs_metrics_object", "processing_jobs", "jsonb_typeof(metrics) = 'object'"
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("current_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rss_bytes", sa.BigInteger(), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("worker_id", name="pk_worker_heartbeats"),
        sa.CheckConstraint(
            "state IN ('STARTING', 'IDLE', 'BUSY', 'STOPPING', 'STOPPED')",
            name="ck_worker_heartbeats_state",
        ),
        sa.CheckConstraint(
            "heartbeat_at >= started_at", name="ck_worker_heartbeats_heartbeat_after_start"
        ),
        sa.CheckConstraint(
            "(rss_bytes IS NULL OR rss_bytes >= 0) AND (cpu_percent IS NULL OR cpu_percent >= 0)",
            name="ck_worker_heartbeats_resources_nonnegative",
        ),
    )
    op.create_index(
        "ix_worker_heartbeats_heartbeat_at", "worker_heartbeats", ["heartbeat_at"]
    )


def downgrade():
    op.drop_index("ix_worker_heartbeats_heartbeat_at", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_constraint("ck_jobs_metrics_object", "processing_jobs", type_="check")
    op.drop_column("processing_jobs", "metrics_updated_at")
    op.drop_column("processing_jobs", "metrics")
