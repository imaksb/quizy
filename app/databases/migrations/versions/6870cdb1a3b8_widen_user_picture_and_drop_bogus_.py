"""widen user.picture and drop bogus unique constraints

Revision ID: 6870cdb1a3b8
Revises: 90eb342b9721
Create Date: 2026-04-19 08:23:22.551495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6870cdb1a3b8'
down_revision: Union[str, Sequence[str], None] = '90eb342b9721'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'user', 'email',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        'user', 'name',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        'user', 'picture',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.VARCHAR(length=2048),
        existing_nullable=True,
    )
    op.drop_constraint(op.f('user_email_verified_key'), 'user', type_='unique')
    op.drop_constraint(op.f('user_name_key'), 'user', type_='unique')
    op.drop_constraint(op.f('user_picture_key'), 'user', type_='unique')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_unique_constraint(
        op.f('user_picture_key'), 'user', ['picture'],
        postgresql_nulls_not_distinct=False,
    )
    op.create_unique_constraint(
        op.f('user_name_key'), 'user', ['name'],
        postgresql_nulls_not_distinct=False,
    )
    op.create_unique_constraint(
        op.f('user_email_verified_key'), 'user', ['email_verified'],
        postgresql_nulls_not_distinct=False,
    )
    op.alter_column(
        'user', 'picture',
        existing_type=sa.VARCHAR(length=2048),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        'user', 'name',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        'user', 'email',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
