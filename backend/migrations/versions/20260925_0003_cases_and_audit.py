"""Create cases, saved result snapshots and audit logs.

Revision ID: 20260925_0003
Revises: 20260925_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0003"
down_revision: str | None = "20260925_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

audit_result = postgresql.ENUM("SUCCESS", "FAILURE", name="audit_result", create_type=False)


def upgrade() -> None:
    audit_result.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_cases_title_not_blank"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_cases_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
    )
    op.create_index("ix_cases_owner_created_at", "cases", ["owner_user_id", "created_at"])
    op.create_table(
        "case_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_name_snapshot", sa.String(200), nullable=False),
        sa.Column("area_name_snapshot", sa.String(200), nullable=False),
        sa.Column("appeared_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "saved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "length(btrim(camera_name_snapshot)) > 0", name="ck_case_results_camera_name_not_blank"
        ),
        sa.CheckConstraint(
            "length(btrim(area_name_snapshot)) > 0", name="ck_case_results_area_name_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_case_results_case_id_cases", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["person_tracks.id"],
            name="fk_case_results_track_id_person_tracks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_results"),
    )
    op.create_index("ix_case_results_case_saved_at", "case_results", ["case_id", "saved_at"])
    op.create_index("ix_case_results_track_id", "case_results", ["track_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", audit_result, nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(event_type)) > 0", name="ck_audit_event_type_not_blank"),
        sa.CheckConstraint("length(btrim(target_type)) > 0", name="ck_audit_target_type_not_blank"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index(
        "ix_audit_logs_actor_occurred_at", "audit_logs", ["actor_user_id", "occurred_at"]
    )
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])

    op.execute(
        "CREATE TRIGGER trg_cases_updated_at BEFORE UPDATE ON cases "
        "FOR EACH ROW EXECUTE FUNCTION set_row_updated_at()"
    )
    op.execute("""
        CREATE FUNCTION enforce_case_operator_owner() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM users
                WHERE id = NEW.owner_user_id AND role = 'OPERATOR'
            ) THEN
                RAISE EXCEPTION 'Case owner must be an Operator';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_cases_operator_owner BEFORE INSERT OR UPDATE OF owner_user_id "
        "ON cases FOR EACH ROW EXECUTE FUNCTION enforce_case_operator_owner()"
    )
    op.execute("""
        CREATE FUNCTION reject_case_result_update() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'CaseResult snapshot is immutable'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_case_results_immutable BEFORE UPDATE ON case_results "
        "FOR EACH ROW EXECUTE FUNCTION reject_case_result_update()"
    )
    op.execute("""
        CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'AuditLog is append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_case_results_immutable ON case_results")
    op.execute("DROP FUNCTION IF EXISTS reject_case_result_update()")
    op.execute("DROP TRIGGER IF EXISTS trg_cases_operator_owner ON cases")
    op.execute("DROP FUNCTION IF EXISTS enforce_case_operator_owner()")
    op.execute("DROP TRIGGER IF EXISTS trg_cases_updated_at ON cases")
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_occurred_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_case_results_track_id", table_name="case_results")
    op.drop_index("ix_case_results_case_saved_at", table_name="case_results")
    op.drop_table("case_results")
    op.drop_index("ix_cases_owner_created_at", table_name="cases")
    op.drop_table("cases")
    audit_result.drop(op.get_bind(), checkfirst=True)
