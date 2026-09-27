"""Case status: OPEN (being handled) or CLOSED (completed, locked until reopened).

Revision ID: 20260927_0013
Revises: 20260926_0012
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260927_0013"
down_revision = "20260926_0012"
branch_labels = None
depends_on = None

case_status = postgresql.ENUM("OPEN", "CLOSED", name="case_status", create_type=False)


def upgrade():
    case_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "cases",
        sa.Column("status", case_status, nullable=False, server_default="OPEN"),
    )
    op.add_column("cases", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_cases_closed_at_matches_status",
        "cases",
        "(status = 'CLOSED') = (closed_at IS NOT NULL)",
    )
    op.create_index("ix_cases_status", "cases", ["status"])


def downgrade():
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_constraint("ck_cases_closed_at_matches_status", "cases", type_="check")
    op.drop_column("cases", "closed_at")
    op.drop_column("cases", "status")
    case_status.drop(op.get_bind(), checkfirst=True)
