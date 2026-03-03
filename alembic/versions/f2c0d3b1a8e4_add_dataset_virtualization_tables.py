"""add dataset virtualization tables

Revision ID: f2c0d3b1a8e4
Revises: c31f2da9e4b2
Create Date: 2026-03-03 16:20:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c0d3b1a8e4"
down_revision = "c31f2da9e4b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("dataset_type", sa.String(length=32), nullable=False),
        sa.Column("dialect", sa.String(length=64), nullable=True),
        sa.Column("catalog_name", sa.String(length=255), nullable=True),
        sa.Column("schema_name", sa.String(length=255), nullable=True),
        sa.Column("table_name", sa.String(length=255), nullable=True),
        sa.Column("sql_text", sa.Text(), nullable=True),
        sa.Column("referenced_dataset_ids_json", sa.JSON(), nullable=False),
        sa.Column("federated_plan_json", sa.JSON(), nullable=True),
        sa.Column("file_config_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=True),
        sa.Column("row_count_estimate", sa.BigInteger(), nullable=True),
        sa.Column("bytes_estimate", sa.BigInteger(), nullable=True),
        sa.Column("last_profiled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connectors.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_datasets_workspace_name"),
    )
    op.create_index(op.f("ix_datasets_workspace_id"), "datasets", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_datasets_project_id"), "datasets", ["project_id"], unique=False)
    op.create_index(op.f("ix_datasets_connection_id"), "datasets", ["connection_id"], unique=False)
    op.create_index(op.f("ix_datasets_dataset_type"), "datasets", ["dataset_type"], unique=False)
    op.create_index(op.f("ix_datasets_updated_at"), "datasets", ["updated_at"], unique=False)
    op.create_index("ix_datasets_workspace_name", "datasets", ["workspace_id", "name"], unique=False)
    op.create_index(
        "ix_datasets_workspace_updated_at",
        "datasets",
        ["workspace_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "dataset_columns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=128), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("is_allowed", sa.Boolean(), nullable=False),
        sa.Column("is_computed", sa.Boolean(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(["workspace_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "name", name="uq_dataset_columns_dataset_name"),
    )
    op.create_index(op.f("ix_dataset_columns_dataset_id"), "dataset_columns", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_dataset_columns_workspace_id"), "dataset_columns", ["workspace_id"], unique=False)
    op.create_index(
        "ix_dataset_columns_dataset_ordinal",
        "dataset_columns",
        ["dataset_id", "ordinal_position"],
        unique=False,
    )

    op.create_table(
        "dataset_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("max_rows_preview", sa.Integer(), nullable=False),
        sa.Column("max_export_rows", sa.Integer(), nullable=False),
        sa.Column("redaction_rules_json", sa.JSON(), nullable=False),
        sa.Column("row_filters_json", sa.JSON(), nullable=False),
        sa.Column("allow_dml", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(["workspace_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id"),
    )
    op.create_index(op.f("ix_dataset_policies_dataset_id"), "dataset_policies", ["dataset_id"], unique=True)
    op.create_index(op.f("ix_dataset_policies_workspace_id"), "dataset_policies", ["workspace_id"], unique=False)

    op.create_table(
        "dataset_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(["workspace_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "revision_number", name="uq_dataset_revisions_number"),
    )
    op.create_index(op.f("ix_dataset_revisions_dataset_id"), "dataset_revisions", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_dataset_revisions_workspace_id"), "dataset_revisions", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataset_revisions_workspace_id"), table_name="dataset_revisions")
    op.drop_index(op.f("ix_dataset_revisions_dataset_id"), table_name="dataset_revisions")
    op.drop_table("dataset_revisions")

    op.drop_index(op.f("ix_dataset_policies_workspace_id"), table_name="dataset_policies")
    op.drop_index(op.f("ix_dataset_policies_dataset_id"), table_name="dataset_policies")
    op.drop_table("dataset_policies")

    op.drop_index("ix_dataset_columns_dataset_ordinal", table_name="dataset_columns")
    op.drop_index(op.f("ix_dataset_columns_workspace_id"), table_name="dataset_columns")
    op.drop_index(op.f("ix_dataset_columns_dataset_id"), table_name="dataset_columns")
    op.drop_table("dataset_columns")

    op.drop_index("ix_datasets_workspace_updated_at", table_name="datasets")
    op.drop_index("ix_datasets_workspace_name", table_name="datasets")
    op.drop_index(op.f("ix_datasets_updated_at"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_dataset_type"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_connection_id"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_project_id"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_workspace_id"), table_name="datasets")
    op.drop_table("datasets")
