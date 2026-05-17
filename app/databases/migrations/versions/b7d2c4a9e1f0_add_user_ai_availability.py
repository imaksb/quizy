"""Add user AI availability

Revision ID: b7d2c4a9e1f0
Revises: 6870cdb1a3b8, a1c8d9e7f2b4
Create Date: 2026-05-17 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2c4a9e1f0"
down_revision: str | Sequence[str] | None = (
    "6870cdb1a3b8",
    "a1c8d9e7f2b4",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
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
    op.drop_column("user", "is_ai_available")
