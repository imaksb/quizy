"""Add session reconnect constraints

Revision ID: f3a8f7d6c9b2
Revises: 90eb342b9721
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f3a8f7d6c9b2"
down_revision: Union[str, Sequence[str], None] = "90eb342b9721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_quizsession_join_code"), table_name="quizsession")
    op.create_index(
        op.f("ix_quizsession_join_code"),
        "quizsession",
        ["join_code"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_sessionparticipant_session_guest_token",
        "sessionparticipant",
        ["session_id", "guest_token"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_sessionparticipant_session_guest_token",
        "sessionparticipant",
        type_="unique",
    )
    op.drop_index(op.f("ix_quizsession_join_code"), table_name="quizsession")
    op.create_index(
        op.f("ix_quizsession_join_code"),
        "quizsession",
        ["join_code"],
        unique=False,
    )
