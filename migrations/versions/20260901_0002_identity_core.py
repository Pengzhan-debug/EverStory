"""Add guest auth sessions and explicit tenant ownership."""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0002"
down_revision = "20260901_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    op.add_column("users", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column(
        "users", sa.Column("display_name", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE users SET updated_at = CURRENT_TIMESTAMP, "
        "last_seen_at = CURRENT_TIMESTAMP"
    )
    if dialect != "sqlite":
        op.alter_column("users", "updated_at", nullable=False)
        op.alter_column("users", "last_seen_at", nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    op.add_column(
        "save_games", sa.Column("user_id", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "llm_usage_events", sa.Column("user_id", sa.String(length=32), nullable=True)
    )
    op.execute(
        "UPDATE save_games SET user_id = "
        "(SELECT player_sessions.user_id FROM player_sessions "
        "WHERE player_sessions.id = save_games.session_id)"
    )
    op.execute(
        "UPDATE llm_usage_events SET user_id = "
        "(SELECT player_sessions.user_id FROM player_sessions "
        "WHERE player_sessions.id = llm_usage_events.session_id)"
    )
    if dialect != "sqlite":
        op.alter_column("save_games", "user_id", nullable=False)
        op.alter_column("llm_usage_events", "user_id", nullable=False)
    op.create_index("ix_save_games_user_id", "save_games", ["user_id"])
    op.create_index(
        "ix_llm_usage_events_user_id", "llm_usage_events", ["user_id"]
    )

    # SQLite remains a deterministic test backend; production PostgreSQL gets
    # explicit FK constraints for the newly backfilled tenant columns.
    if dialect == "postgresql":
        op.create_foreign_key(
            "fk_save_games_user_id", "save_games", "users", ["user_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_llm_usage_events_user_id",
            "llm_usage_events",
            "users",
            ["user_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "fk_llm_usage_events_user_id", "llm_usage_events", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_save_games_user_id", "save_games", type_="foreignkey"
        )
    op.drop_index("ix_llm_usage_events_user_id", table_name="llm_usage_events")
    op.drop_index("ix_save_games_user_id", table_name="save_games")
    op.drop_column("llm_usage_events", "user_id")
    op.drop_column("save_games", "user_id")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
