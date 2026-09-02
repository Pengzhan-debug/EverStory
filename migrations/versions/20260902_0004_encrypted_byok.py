"""Add encrypted account-scoped player LLM profiles."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_0004"
down_revision = "20260901_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_profiles",
        sa.Column("user_id", sa.String(length=32), primary_key=True),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("platform_connection_ids", sa.JSON(), nullable=False),
        sa.Column("agent_routes", sa.JSON(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
        sa.Column("wrapped_data_key", sa.Text(), nullable=True),
        sa.Column("payload_nonce", sa.String(length=32), nullable=True),
        sa.Column("wrap_nonce", sa.String(length=32), nullable=True),
        sa.Column("key_id", sa.String(length=80), nullable=True),
        sa.Column("algorithm", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("user_llm_profiles")
