"""Camera optimistic locking and private connection state."""

import sqlalchemy as sa
from alembic import op

revision = "20260925_0007"
down_revision = "20260925_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cameras", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("cameras", sa.Column("last_checked_at", sa.DateTime(timezone=True)))
    op.add_column("cameras", sa.Column("rtsp_credentials", sa.Text()))
    op.create_check_constraint("ck_cameras_version_positive", "cameras", "version > 0")


def downgrade():
    op.drop_constraint("ck_cameras_version_positive", "cameras", type_="check")
    for name in ("rtsp_credentials", "last_checked_at", "version"):
        op.drop_column("cameras", name)
