"""add enable_thinking to conversations

Revision ID: 2b075199f95c
Revises: 21a0bdac63d2
Create Date: 2026-06-25 01:22:47.667237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b075199f95c'
down_revision: Union[str, Sequence[str], None] = '21a0bdac63d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('conversations', sa.Column('enable_thinking', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('conversations', 'enable_thinking')
