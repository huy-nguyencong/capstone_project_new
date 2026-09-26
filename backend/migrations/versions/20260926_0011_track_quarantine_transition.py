"""Allow reconciliation to quarantine a corrupt READY track.

Revision ID: 20260926_0011
Revises: 20260926_0010
"""

from alembic import op

revision = "20260926_0011"
down_revision = "20260926_0010"
branch_labels = None
depends_on = None


def _replace_function(*, allow_quarantine: bool) -> None:
    ready_clause = " OR (OLD.index_status = 'READY' AND NEW.index_status = 'FAILED')"
    if not allow_quarantine:
        ready_clause = ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION enforce_track_index_transition() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.index_status <> 'PENDING' THEN
                RAISE EXCEPTION 'PersonTrack must be created as PENDING';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.index_status IS DISTINCT FROM OLD.index_status AND NOT (
                (OLD.index_status = 'PENDING' AND NEW.index_status IN ('READY', 'FAILED')) OR
                (OLD.index_status = 'FAILED' AND NEW.index_status = 'PENDING')
                {ready_clause}
            ) THEN
                RAISE EXCEPTION 'Invalid PersonTrack index status transition: % -> %',
                    OLD.index_status, NEW.index_status;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
        """
    )


def upgrade() -> None:
    _replace_function(allow_quarantine=True)


def downgrade() -> None:
    _replace_function(allow_quarantine=False)
