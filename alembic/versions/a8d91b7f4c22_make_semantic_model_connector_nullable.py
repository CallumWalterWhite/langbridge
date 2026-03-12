"""make semantic model connector nullable

Revision ID: a8d91b7f4c22
Revises: e6f9a1b2c3d4
Create Date: 2026-03-12 12:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a8d91b7f4c22"
down_revision = "e6f9a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("semantic_models", "connector_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("semantic_models", "connector_id", existing_type=sa.UUID(), nullable=False)
