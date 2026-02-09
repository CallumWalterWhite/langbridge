"""add dashboard refresh and snapshot columns

Revision ID: 1a8ec5672a11
Revises: 6f33689ff0f1
Create Date: 2026-02-09 18:10:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a8ec5672a11"
down_revision = "6f33689ff0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bi_dashboards",
        sa.Column("refresh_mode", sa.String(length=32), nullable=False, server_default="manual"),
    )
    op.add_column(
        "bi_dashboards",
        sa.Column("data_snapshot_format", sa.String(length=32), nullable=False, server_default="json"),
    )
    op.add_column(
        "bi_dashboards",
        sa.Column("data_snapshot_reference", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "bi_dashboards",
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bi_dashboards", "last_refreshed_at")
    op.drop_column("bi_dashboards", "data_snapshot_reference")
    op.drop_column("bi_dashboards", "data_snapshot_format")
    op.drop_column("bi_dashboards", "refresh_mode")
