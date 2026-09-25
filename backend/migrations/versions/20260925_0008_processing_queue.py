"""Durable upload idempotency, cancellation and worker leases."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0008"
down_revision = "20260925_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("person_tracks", sa.Column("source_frame_index", sa.BigInteger()))
    for column in (
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("request_digest", sa.String(64)),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sampled_frames", sa.Integer(), nullable=False, server_default="0"),
    ):
        op.add_column("processing_jobs", column)
    op.create_index(
        "uq_jobs_actor_idempotency",
        "processing_jobs",
        ["requested_by", "idempotency_key"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_jobs_worker_counters", "processing_jobs", "attempts >= 0 AND sampled_frames >= 0"
    )


def downgrade():
    op.drop_column("person_tracks", "source_frame_index")
    op.drop_constraint("ck_jobs_worker_counters", "processing_jobs", type_="check")
    op.drop_index("uq_jobs_actor_idempotency", table_name="processing_jobs")
    op.drop_constraint(
        "fk_processing_jobs_requested_by_users", "processing_jobs", type_="foreignkey"
    )
    for name in (
        "requested_by",
        "idempotency_key",
        "request_digest",
        "cancel_requested",
        "lease_token",
        "heartbeat_at",
        "lease_expires_at",
        "attempts",
        "sampled_frames",
    ):
        op.drop_column("processing_jobs", name)
