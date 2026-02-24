"""add conversation memory items

Revision ID: 2c5f4dd8b3d0
Revises: 1a8ec5672a11
Create Date: 2026-02-24 12:25:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "2c5f4dd8b3d0"
down_revision = "1a8ec5672a11"
branch_labels = None
depends_on = None


_MEMORY_CATEGORY_ENUM = postgresql.ENUM(
    "fact",
    "preference",
    "decision",
    "tool_outcome",
    "answer",
    name="memory_category",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    category_type: sa.TypeEngine
    if bind.dialect.name == "postgresql":
        _MEMORY_CATEGORY_ENUM.create(bind, checkfirst=True)
        category_type = _MEMORY_CATEGORY_ENUM
    else:
        category_type = sa.Enum(
            "fact",
            "preference",
            "decision",
            "tool_outcome",
            "answer",
            name="memory_category",
        )

    op.create_table(
        "conversation_memory_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("category", category_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_conversation_memory_items_thread_id"),
        "conversation_memory_items",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_memory_items_user_id"),
        "conversation_memory_items",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_memory_items_category"),
        "conversation_memory_items",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_memory_items_created_at"),
        "conversation_memory_items",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_memory_items_last_accessed_at"),
        "conversation_memory_items",
        ["last_accessed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_memory_items_last_accessed_at"), table_name="conversation_memory_items")
    op.drop_index(op.f("ix_conversation_memory_items_created_at"), table_name="conversation_memory_items")
    op.drop_index(op.f("ix_conversation_memory_items_category"), table_name="conversation_memory_items")
    op.drop_index(op.f("ix_conversation_memory_items_user_id"), table_name="conversation_memory_items")
    op.drop_index(op.f("ix_conversation_memory_items_thread_id"), table_name="conversation_memory_items")
    op.drop_table("conversation_memory_items")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _MEMORY_CATEGORY_ENUM.drop(bind, checkfirst=True)
