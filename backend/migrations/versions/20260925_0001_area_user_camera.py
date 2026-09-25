"""Create areas, users and cameras.

Revision ID: 20260925_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("ADMIN", "OPERATOR", "VIEWER", name="user_role", create_type=False)
user_status = postgresql.ENUM(
    "ACTIVE", "LOCKED", "INACTIVE", "DELETED", name="user_status", create_type=False
)
camera_status = postgresql.ENUM(
    "ACTIVE", "INACTIVE", "RETIRED", name="camera_status", create_type=False
)
rtsp_status = postgresql.ENUM(
    "UNKNOWN", "ONLINE", "OFFLINE", "ERROR", name="rtsp_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    user_status.create(bind, checkfirst=True)
    camera_status.create(bind, checkfirst=True)
    rtsp_status.create(bind, checkfirst=True)

    op.create_table(
        "areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
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
        sa.CheckConstraint("code = upper(code)", name="ck_areas_code_uppercase"),
        sa.CheckConstraint("length(btrim(code)) > 0", name="ck_areas_code_not_blank"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_areas_name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_areas"),
        sa.UniqueConstraint("code", name="uq_areas_code"),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column(
            "status", user_status, server_default=sa.text("'ACTIVE'::user_status"), nullable=False
        ),
        sa.Column("assigned_area_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint("length(btrim(username)) > 0", name="ck_users_username_not_blank"),
        sa.CheckConstraint(
            "length(btrim(password_hash)) > 0", name="ck_users_password_hash_not_blank"
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0", name="ck_users_display_name_not_blank"
        ),
        sa.CheckConstraint(
            "(role = 'OPERATOR' AND assigned_area_id IS NOT NULL) OR "
            "(role IN ('ADMIN', 'VIEWER') AND assigned_area_id IS NULL)",
            name="ck_users_role_assigned_area",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_area_id"],
            ["areas.id"],
            name="fk_users_assigned_area_id_areas",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_assigned_area_id", "users", ["assigned_area_id"])
    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rtsp_url", sa.String(length=2048), nullable=True),
        sa.Column("rtsp_secret_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            camera_status,
            server_default=sa.text("'ACTIVE'::camera_status"),
            nullable=False,
        ),
        sa.Column(
            "rtsp_status",
            rtsp_status,
            server_default=sa.text("'UNKNOWN'::rtsp_status"),
            nullable=False,
        ),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.CheckConstraint("code = upper(code)", name="ck_cameras_code_uppercase"),
        sa.CheckConstraint("length(btrim(code)) > 0", name="ck_cameras_code_not_blank"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_cameras_name_not_blank"),
        sa.CheckConstraint(
            "rtsp_url IS NULL OR rtsp_url ~ '^rtsps?://'", name="ck_cameras_rtsp_scheme"
        ),
        sa.CheckConstraint(
            "rtsp_url IS NULL OR rtsp_url !~ '^rtsps?://[^/]*@'",
            name="ck_cameras_rtsp_no_embedded_credentials",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"], ["areas.id"], name="fk_cameras_area_id_areas", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cameras"),
        sa.UniqueConstraint("code", name="uq_cameras_code"),
    )
    op.create_index("ix_cameras_area_id", "cameras", ["area_id"])

    op.execute("""
        CREATE FUNCTION set_row_updated_at() RETURNS trigger AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    for table_name in ("areas", "users", "cameras"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_updated_at BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION set_row_updated_at()"
        )
    op.execute("""
        CREATE FUNCTION reject_area_code_change() RETURNS trigger AS $$
        BEGIN
            IF NEW.code IS DISTINCT FROM OLD.code THEN
                RAISE EXCEPTION 'Area.code is immutable after creation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_areas_code_immutable BEFORE UPDATE ON areas "
        "FOR EACH ROW EXECUTE FUNCTION reject_area_code_change()"
    )
    op.execute("""
        CREATE FUNCTION reject_camera_identity_change() RETURNS trigger AS $$
        BEGIN
            IF NEW.area_id IS DISTINCT FROM OLD.area_id THEN
                RAISE EXCEPTION 'Camera.area_id is immutable after creation';
            END IF;
            IF NEW.code IS DISTINCT FROM OLD.code THEN
                RAISE EXCEPTION 'Camera.code is immutable after creation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_cameras_identity_immutable BEFORE UPDATE ON cameras "
        "FOR EACH ROW EXECUTE FUNCTION reject_camera_identity_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_cameras_identity_immutable ON cameras")
    op.execute("DROP FUNCTION IF EXISTS reject_camera_identity_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_areas_code_immutable ON areas")
    op.execute("DROP FUNCTION IF EXISTS reject_area_code_change()")
    for table_name in ("cameras", "users", "areas"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS set_row_updated_at()")
    op.drop_index("ix_cameras_area_id", table_name="cameras")
    op.drop_table("cameras")
    op.drop_index("ix_users_assigned_area_id", table_name="users")
    op.drop_table("users")
    op.drop_table("areas")
    bind = op.get_bind()
    rtsp_status.drop(bind, checkfirst=True)
    camera_status.drop(bind, checkfirst=True)
    user_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
