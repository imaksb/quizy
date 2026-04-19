"""Add session result tables

Revision ID: a1c8d9e7f2b4
Revises: f3a8f7d6c9b2
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1c8d9e7f2b4"
down_revision: Union[str, Sequence[str], None] = "f3a8f7d6c9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sessionresult",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("quiz_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("total_players", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quiz_id"], ["quiz.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["quizsession.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_sessionresult_owner_id"), "sessionresult", ["owner_id"], unique=False)
    op.create_index(op.f("ix_sessionresult_quiz_id"), "sessionresult", ["quiz_id"], unique=False)
    op.create_index(op.f("ix_sessionresult_session_id"), "sessionresult", ["session_id"], unique=True)

    op.create_table(
        "sessionplayerresult",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_result_id", sa.UUID(), nullable=False),
        sa.Column("participant_id", sa.UUID(), nullable=False),
        sa.Column("guest_name", sa.String(length=255), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("final_rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["session_result_id"], ["sessionresult.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        op.f("ix_sessionplayerresult_participant_id"),
        "sessionplayerresult",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sessionplayerresult_session_result_id"),
        "sessionplayerresult",
        ["session_result_id"],
        unique=False,
    )

    op.create_table(
        "sessionanswerresult",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("player_result_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("selected_answer_option_ids", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.BOOLEAN(), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=False),
        sa.Column("answered_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["player_result_id"], ["sessionplayerresult.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        op.f("ix_sessionanswerresult_player_result_id"),
        "sessionanswerresult",
        ["player_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sessionanswerresult_question_id"),
        "sessionanswerresult",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_sessionanswerresult_question_id"), table_name="sessionanswerresult")
    op.drop_index(op.f("ix_sessionanswerresult_player_result_id"), table_name="sessionanswerresult")
    op.drop_table("sessionanswerresult")
    op.drop_index(op.f("ix_sessionplayerresult_session_result_id"), table_name="sessionplayerresult")
    op.drop_index(op.f("ix_sessionplayerresult_participant_id"), table_name="sessionplayerresult")
    op.drop_table("sessionplayerresult")
    op.drop_index(op.f("ix_sessionresult_session_id"), table_name="sessionresult")
    op.drop_index(op.f("ix_sessionresult_quiz_id"), table_name="sessionresult")
    op.drop_index(op.f("ix_sessionresult_owner_id"), table_name="sessionresult")
    op.drop_table("sessionresult")
