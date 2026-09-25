"""Create AI configs, processing jobs, person tracks and storage outbox.

Revision ID: 20260925_0002
Revises: 20260925_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0002"
down_revision: str | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ai_config_status = postgresql.ENUM(
    "DRAFT", "ACTIVE", "RETIRED", name="ai_config_status", create_type=False
)
job_source_type = postgresql.ENUM("FILE", "RTSP", name="job_source_type", create_type=False)
job_status = postgresql.ENUM(
    "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", name="job_status", create_type=False
)
track_index_status = postgresql.ENUM(
    "PENDING", "READY", "FAILED", name="track_index_status", create_type=False
)
outbox_status = postgresql.ENUM(
    "PENDING", "PROCESSING", "COMPLETED", "DEAD", name="outbox_status", create_type=False
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        ai_config_status,
        job_source_type,
        job_status,
        track_index_status,
        outbox_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "ai_config_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("detector_name", sa.String(100), nullable=False),
        sa.Column("detector_version", sa.String(100), nullable=False),
        sa.Column("tracker_name", sa.String(100), nullable=False),
        sa.Column("tracker_version", sa.String(100), nullable=False),
        sa.Column("encoder_name", sa.String(100), nullable=False),
        sa.Column("encoder_version", sa.String(100), nullable=False),
        sa.Column("encoder_dimension", sa.Integer(), nullable=False),
        sa.Column("checkpoint_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            ai_config_status,
            server_default=sa.text("'DRAFT'::ai_config_status"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint("encoder_dimension > 0", name="ck_ai_config_encoder_dimension_positive"),
        sa.CheckConstraint(
            "checkpoint_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_config_checkpoint_sha256"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_config_versions"),
        sa.UniqueConstraint("version", name="uq_ai_config_versions_version"),
    )
    op.create_index(
        "uq_ai_config_single_active",
        "ai_config_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_config_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", job_source_type, nullable=False),
        sa.Column("source_ref", sa.String(2048), nullable=True),
        sa.Column(
            "status", job_status, server_default=sa.text("'PENDING'::job_status"), nullable=False
        ),
        sa.Column("sampling_interval", sa.Integer(), nullable=False),
        sa.Column("timeline_origin_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_frames", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_frames", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sampling_interval > 0", name="ck_jobs_sampling_interval_positive"),
        sa.CheckConstraint("processed_frames >= 0", name="ck_jobs_processed_frames_nonnegative"),
        sa.CheckConstraint(
            "total_frames IS NULL OR total_frames >= processed_frames",
            name="ck_jobs_total_frames_progress",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_jobs_ended_after_started",
        ),
        sa.CheckConstraint(
            "source_type <> 'FILE' OR source_ref IS NOT NULL", name="ck_jobs_file_source_ref"
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_processing_jobs_camera_id_cameras",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_config_version_id"],
            ["ai_config_versions.id"],
            name="fk_processing_jobs_ai_config_version_id_ai_config_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_jobs"),
    )
    op.create_index("ix_processing_jobs_camera_id", "processing_jobs", ["camera_id"])
    op.create_index(
        "ix_processing_jobs_ai_config_version_id", "processing_jobs", ["ai_config_version_id"]
    )
    op.create_table(
        "person_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processing_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_config_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appeared_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_started_at_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_ended_at_ms", sa.BigInteger(), nullable=False),
        sa.Column("representative_frame_timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("bbox_x", sa.Integer(), nullable=False),
        sa.Column("bbox_y", sa.Integer(), nullable=False),
        sa.Column("bbox_width", sa.Integer(), nullable=False),
        sa.Column("bbox_height", sa.Integer(), nullable=False),
        sa.Column("frame_width", sa.Integer(), nullable=False),
        sa.Column("frame_height", sa.Integer(), nullable=False),
        sa.Column("minio_object_key", sa.String(1024), nullable=True),
        sa.Column("frame_sha256", sa.String(64), nullable=True),
        sa.Column("frame_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("encoder_version", sa.String(100), nullable=False),
        sa.Column("vector_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "index_status",
            track_index_status,
            server_default=sa.text("'PENDING'::track_index_status"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("source_started_at_ms >= 0", name="ck_tracks_source_start_nonnegative"),
        sa.CheckConstraint(
            "source_ended_at_ms >= source_started_at_ms", name="ck_tracks_source_end_order"
        ),
        sa.CheckConstraint(
            "representative_frame_timestamp_ms BETWEEN source_started_at_ms AND source_ended_at_ms",
            name="ck_tracks_representative_timestamp_range",
        ),
        sa.CheckConstraint("bbox_x >= 0 AND bbox_y >= 0", name="ck_tracks_bbox_origin"),
        sa.CheckConstraint("bbox_width > 0 AND bbox_height > 0", name="ck_tracks_bbox_size"),
        sa.CheckConstraint("frame_width > 0 AND frame_height > 0", name="ck_tracks_frame_size"),
        sa.CheckConstraint(
            "bbox_x + bbox_width <= frame_width AND bbox_y + bbox_height <= frame_height",
            name="ck_tracks_bbox_within_frame",
        ),
        sa.CheckConstraint(
            "frame_sha256 IS NULL OR frame_sha256 ~ '^[0-9a-f]{64}$'", name="ck_tracks_frame_sha256"
        ),
        sa.CheckConstraint(
            "index_status <> 'READY' OR (minio_object_key IS NOT NULL AND "
            "frame_sha256 IS NOT NULL AND frame_size_bytes > 0 AND "
            "vector_indexed_at IS NOT NULL)",
            name="ck_tracks_ready_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"],
            ["cameras.id"],
            name="fk_person_tracks_camera_id_cameras",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["processing_job_id"],
            ["processing_jobs.id"],
            name="fk_person_tracks_processing_job_id_processing_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_config_version_id"],
            ["ai_config_versions.id"],
            name="fk_person_tracks_ai_config_version_id_ai_config_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_person_tracks"),
    )
    for column in ("camera_id", "processing_job_id", "ai_config_version_id", "appeared_at_utc"):
        op.create_index(f"ix_person_tracks_{column}", "person_tracks", [column])
    op.create_table(
        "storage_outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            outbox_status,
            server_default=sa.text("'PENDING'::outbox_status"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_attempts_nonnegative"),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["person_tracks.id"],
            name="fk_storage_outbox_events_track_id_person_tracks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_storage_outbox_events"),
        sa.UniqueConstraint("track_id", "event_type", name="uq_outbox_track_event_type"),
    )
    op.create_index("ix_storage_outbox_events_track_id", "storage_outbox_events", ["track_id"])

    for table_name in (
        "ai_config_versions",
        "processing_jobs",
        "person_tracks",
        "storage_outbox_events",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_updated_at BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION set_row_updated_at()"
        )
    op.execute("""
        CREATE FUNCTION enforce_track_index_transition() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.index_status <> 'PENDING' THEN
                RAISE EXCEPTION 'PersonTrack must be created as PENDING';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.index_status IS DISTINCT FROM OLD.index_status AND NOT (
                (OLD.index_status = 'PENDING' AND NEW.index_status IN ('READY', 'FAILED')) OR
                (OLD.index_status = 'FAILED' AND NEW.index_status = 'PENDING')
            ) THEN
                RAISE EXCEPTION 'Invalid PersonTrack index status transition: % -> %',
                    OLD.index_status, NEW.index_status;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_person_tracks_index_transition BEFORE INSERT OR UPDATE "
        "ON person_tracks FOR EACH ROW EXECUTE FUNCTION enforce_track_index_transition()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_person_tracks_index_transition ON person_tracks")
    op.execute("DROP FUNCTION IF EXISTS enforce_track_index_transition()")
    for table_name in (
        "storage_outbox_events",
        "person_tracks",
        "processing_jobs",
        "ai_config_versions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name}")
    op.drop_index("ix_storage_outbox_events_track_id", table_name="storage_outbox_events")
    op.drop_table("storage_outbox_events")
    for column in ("appeared_at_utc", "ai_config_version_id", "processing_job_id", "camera_id"):
        op.drop_index(f"ix_person_tracks_{column}", table_name="person_tracks")
    op.drop_table("person_tracks")
    op.drop_index("ix_processing_jobs_ai_config_version_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_camera_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("uq_ai_config_single_active", table_name="ai_config_versions")
    op.drop_table("ai_config_versions")
    bind = op.get_bind()
    for enum_type in (
        outbox_status,
        track_index_status,
        job_status,
        job_source_type,
        ai_config_status,
    ):
        enum_type.drop(bind, checkfirst=True)
