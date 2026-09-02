"""Add email login challenges for registered account upgrades."""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0003"
down_revision = "20260901_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_challenges",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_login_challenges_email_hash", "login_challenges", ["email_hash"]
    )
    op.create_index(
        "ix_login_challenges_expires_at", "login_challenges", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_challenges_expires_at", table_name="login_challenges"
    )
    op.drop_index(
        "ix_login_challenges_email_hash", table_name="login_challenges"
    )
    op.drop_table("login_challenges")
