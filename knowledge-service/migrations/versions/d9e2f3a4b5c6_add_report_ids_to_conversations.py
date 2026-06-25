"""add report_ids to conversations

Revision ID: d9e2f3a4b5c6
Revises: c8f1a2b3d4e5
Create Date: 2026-06-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d9e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8f1a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "report_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.execute(
        """
        UPDATE conversations
        SET report_ids = jsonb_build_array(report_id::text)
        WHERE report_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("conversations", "report_ids")
