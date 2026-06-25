"""add assistants table and link conversations

Revision ID: e1f2a3b4c5d6
Revises: d9e2f3a4b5c6
Create Date: 2026-06-25 16:00:00.000000

"""
from typing import Sequence, Union
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d9e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default="新助手"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "dataset_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "report_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("enable_thinking", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enable_thinking", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_assistants_tenant_id", "assistants", ["tenant_id"])
    op.create_index("ix_assistants_user_id", "assistants", ["user_id"])

    op.add_column(
        "conversations",
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_assistant_id",
        "conversations",
        "assistants",
        ["assistant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_conversations_assistant_id", "conversations", ["assistant_id"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, tenant_id, user_id, title, dataset_ids, report_ids, report_id,
                   enable_thinking
            FROM conversations
            """
        )
    ).fetchall()

    for row in rows:
        conv_id, tenant_id, user_id, title, dataset_ids, report_ids, report_id, enable_thinking = row
        ds = dataset_ids or []
        rp = list(report_ids or [])
        if report_id and str(report_id) not in [str(x) for x in rp]:
            rp.insert(0, str(report_id))
        name = title if title and title != "新对话" else "默认助手"
        if name.endswith("问答"):
            name = name[:-2] + "助手"
        elif not name.endswith("助手"):
            name = f"{name}助手"

        assistant_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO assistants (
                    id, tenant_id, user_id, name, dataset_ids, report_ids, enable_thinking
                ) VALUES (
                    :id, :tenant_id, :user_id, :name,
                    CAST(:dataset_ids AS jsonb), CAST(:report_ids AS jsonb), :enable_thinking
                )
                """
            ),
            {
                "id": assistant_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "name": name[:200],
                "dataset_ids": json.dumps(ds),
                "report_ids": json.dumps(rp),
                "enable_thinking": enable_thinking if enable_thinking is not None else True,
            },
        )
        conn.execute(
            sa.text("UPDATE conversations SET assistant_id = :aid WHERE id = :cid"),
            {"aid": assistant_id, "cid": conv_id},
        )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_assistant_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_assistant_id", table_name="conversations")
    op.drop_column("conversations", "assistant_id")
    op.drop_index("ix_assistants_user_id", table_name="assistants")
    op.drop_index("ix_assistants_tenant_id", table_name="assistants")
    op.drop_table("assistants")
