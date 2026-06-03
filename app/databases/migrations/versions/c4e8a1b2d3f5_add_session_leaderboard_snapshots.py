"""Add session leaderboard snapshots

Revision ID: c4e8a1b2d3f5
Revises: a1c8d9e7f2b4
Create Date: 2026-06-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "c4e8a1b2d3f5"
down_revision: str | Sequence[str] | None = "b7d2c4a9e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "sessionleaderboardsnapshot" not in table_names:
        op.create_table(
            "sessionleaderboardsnapshot",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("session_id", sa.UUID(), nullable=False),
            sa.Column("question_id", sa.UUID(), nullable=False),
            sa.Column("question_order_index", sa.Integer(), nullable=False),
            sa.Column("delay_seconds", sa.Integer(), nullable=False),
            sa.Column("entries", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["quizsession.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("id"),
            sa.UniqueConstraint(
                "session_id",
                "question_id",
                name="uq_sessionleaderboardsnapshot_session_question",
            ),
        )
        op.create_index(
            op.f("ix_sessionleaderboardsnapshot_session_id"),
            "sessionleaderboardsnapshot",
            ["session_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_sessionleaderboardsnapshot_question_id"),
            "sessionleaderboardsnapshot",
            ["question_id"],
            unique=False,
        )

    user_columns = {
        column["name"] for column in inspector.get_columns("user")
    }
    if "is_ai_available" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "is_ai_available",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "sessionleaderboardsnapshot" in table_names:
        op.drop_index(
            op.f("ix_sessionleaderboardsnapshot_question_id"),
            table_name="sessionleaderboardsnapshot",
        )
        op.drop_index(
            op.f("ix_sessionleaderboardsnapshot_session_id"),
            table_name="sessionleaderboardsnapshot",
        )
        op.drop_table("sessionleaderboardsnapshot")

    user_columns = {
        column["name"] for column in inspector.get_columns("user")
    }
    if "is_ai_available" in user_columns:
        op.drop_column("user", "is_ai_available")
