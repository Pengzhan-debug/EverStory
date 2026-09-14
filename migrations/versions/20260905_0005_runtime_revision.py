"""Fence stale runtime writes with an optimistic revision."""

from alembic import op
import sqlalchemy as sa

revision = "20260905_0005"
down_revision = "20260902_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_sessions", sa.Column("runtime_revision", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("player_sessions", "runtime_revision")
