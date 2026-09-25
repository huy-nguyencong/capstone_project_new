"""Add optimistic-lock version to cases.

Revision ID: 20260925_0009
Revises: 20260925_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0009"
down_revision: str | None = "20260925_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint("ck_cases_version_positive", "cases", "version > 0")


def downgrade() -> None:
    op.drop_constraint("ck_cases_version_positive", "cases", type_="check")
    op.drop_column("cases", "version")
