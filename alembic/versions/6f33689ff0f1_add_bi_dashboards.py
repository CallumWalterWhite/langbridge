"""add bi dashboards

Revision ID: 6f33689ff0f1
Revises: 141a6f030917
Create Date: 2026-02-09 16:45:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f33689ff0f1"
down_revision = "141a6f030917"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bi_dashboards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("semantic_model_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("global_filters", sa.JSON(), nullable=False),
        sa.Column("widgets", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["semantic_model_id"], ["semantic_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bi_dashboards_organization_id"),
        "bi_dashboards",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bi_dashboards_project_id"),
        "bi_dashboards",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_bi_dashboards_project_id"), table_name="bi_dashboards")
    op.drop_index(op.f("ix_bi_dashboards_organization_id"), table_name="bi_dashboards")
    op.drop_table("bi_dashboards")
