"""add user role and display_name

Revision ID: 21a0bdac63d2
Revises: 4dc56b5b074c
Create Date: 2026-06-23 11:19:12.919802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21a0bdac63d2'
down_revision: Union[str, Sequence[str], None] = '4dc56b5b074c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('display_name', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.execute("UPDATE users SET role = 'admin' WHERE scopes::text LIKE '%admin%'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'role')
