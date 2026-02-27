"""add runtime registry and edge gateway tables

Revision ID: 9d5a8a12f983
Revises: 2c5f4dd8b3d0
Create Date: 2026-02-27 10:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d5a8a12f983"
down_revision = "2c5f4dd8b3d0"
branch_labels = None
depends_on = None


runtime_instance_status_enum = sa.Enum(
    "active",
    "draining",
    "offline",
    name="runtime_instance_status",
)

edge_task_status_enum = sa.Enum(
    "queued",
    "leased",
    "acked",
    "failed",
    "dead_letter",
    name="edge_task_status",
)


def upgrade() -> None:
    op.add_column("connectors", sa.Column("connection_metadata_json", sa.JSON(), nullable=True))
    op.add_column("connectors", sa.Column("secret_references_json", sa.JSON(), nullable=True))
    op.add_column("connectors", sa.Column("access_policy_json", sa.JSON(), nullable=True))

    op.create_table(
        "ep_runtime_instances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("status", runtime_instance_status_enum, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ep_runtime_instances_tenant_id"),
        "ep_runtime_instances",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ep_runtime_instances_status"),
        "ep_runtime_instances",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ep_runtime_instances_last_seen_at"),
        "ep_runtime_instances",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_ep_runtime_instances_tenant_status_seen",
        "ep_runtime_instances",
        ["tenant_id", "status", "last_seen_at"],
        unique=False,
    )

    op.create_table(
        "ep_runtime_registration_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runtime_id", sa.UUID(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["runtime_id"], ["ep_runtime_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_ep_runtime_registration_tokens_tenant_id"),
        "ep_runtime_registration_tokens",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ep_runtime_registration_tokens_token_hash"),
        "ep_runtime_registration_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ep_runtime_registration_tokens_expires_at"),
        "ep_runtime_registration_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ep_runtime_registration_tokens_used_at"),
        "ep_runtime_registration_tokens",
        ["used_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ep_runtime_registration_tokens_runtime_id"),
        "ep_runtime_registration_tokens",
        ["runtime_id"],
        unique=False,
    )

    op.create_table(
        "edge_task_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("message_type", sa.String(length=128), nullable=False),
        sa.Column("message_payload", sa.JSON(), nullable=False),
        sa.Column("status", edge_task_status_enum, nullable=False),
        sa.Column("target_runtime_id", sa.UUID(), nullable=True),
        sa.Column("lease_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leased_to_runtime_id", sa.UUID(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.JSON(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_runtime_id"], ["ep_runtime_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edge_task_records_tenant_id"), "edge_task_records", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_edge_task_records_message_type"), "edge_task_records", ["message_type"], unique=False)
    op.create_index(op.f("ix_edge_task_records_status"), "edge_task_records", ["status"], unique=False)
    op.create_index(
        op.f("ix_edge_task_records_target_runtime_id"),
        "edge_task_records",
        ["target_runtime_id"],
        unique=False,
    )
    op.create_index(op.f("ix_edge_task_records_lease_id"), "edge_task_records", ["lease_id"], unique=False)
    op.create_index(
        op.f("ix_edge_task_records_lease_expires_at"),
        "edge_task_records",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_edge_task_records_leased_to_runtime_id"),
        "edge_task_records",
        ["leased_to_runtime_id"],
        unique=False,
    )
    op.create_index(
        "ix_edge_task_records_tenant_status_runtime",
        "edge_task_records",
        ["tenant_id", "status", "target_runtime_id"],
        unique=False,
    )

    op.create_table(
        "edge_result_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("runtime_id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("payload_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["edge_task_records.id"], ondelete="set null"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "runtime_id", "request_id", name="uq_edge_result_receipt_request"),
    )
    op.create_index(
        op.f("ix_edge_result_receipts_tenant_id"),
        "edge_result_receipts",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_edge_result_receipts_runtime_id"),
        "edge_result_receipts",
        ["runtime_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_edge_result_receipts_task_id"),
        "edge_result_receipts",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_edge_result_receipts_task_id"), table_name="edge_result_receipts")
    op.drop_index(op.f("ix_edge_result_receipts_runtime_id"), table_name="edge_result_receipts")
    op.drop_index(op.f("ix_edge_result_receipts_tenant_id"), table_name="edge_result_receipts")
    op.drop_table("edge_result_receipts")

    op.drop_index("ix_edge_task_records_tenant_status_runtime", table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_leased_to_runtime_id"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_lease_expires_at"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_lease_id"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_target_runtime_id"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_status"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_message_type"), table_name="edge_task_records")
    op.drop_index(op.f("ix_edge_task_records_tenant_id"), table_name="edge_task_records")
    op.drop_table("edge_task_records")

    op.drop_index(op.f("ix_ep_runtime_registration_tokens_runtime_id"), table_name="ep_runtime_registration_tokens")
    op.drop_index(op.f("ix_ep_runtime_registration_tokens_used_at"), table_name="ep_runtime_registration_tokens")
    op.drop_index(op.f("ix_ep_runtime_registration_tokens_expires_at"), table_name="ep_runtime_registration_tokens")
    op.drop_index(op.f("ix_ep_runtime_registration_tokens_token_hash"), table_name="ep_runtime_registration_tokens")
    op.drop_index(op.f("ix_ep_runtime_registration_tokens_tenant_id"), table_name="ep_runtime_registration_tokens")
    op.drop_table("ep_runtime_registration_tokens")

    op.drop_index("ix_ep_runtime_instances_tenant_status_seen", table_name="ep_runtime_instances")
    op.drop_index(op.f("ix_ep_runtime_instances_last_seen_at"), table_name="ep_runtime_instances")
    op.drop_index(op.f("ix_ep_runtime_instances_status"), table_name="ep_runtime_instances")
    op.drop_index(op.f("ix_ep_runtime_instances_tenant_id"), table_name="ep_runtime_instances")
    op.drop_table("ep_runtime_instances")

    op.drop_column("connectors", "access_policy_json")
    op.drop_column("connectors", "secret_references_json")
    op.drop_column("connectors", "connection_metadata_json")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        edge_task_status_enum.drop(bind, checkfirst=True)
        runtime_instance_status_enum.drop(bind, checkfirst=True)
