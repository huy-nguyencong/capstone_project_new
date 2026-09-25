"""Add optimistic-lock version to users.

Revision ID: 20260925_0006
Revises: 20260925_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0006"
down_revision: str | None = "20260925_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint("ck_users_version_positive", "users", "version > 0")


def downgrade() -> None:
    op.drop_constraint("ck_users_version_positive", "users", type_="check")
    op.drop_column("users", "version")
