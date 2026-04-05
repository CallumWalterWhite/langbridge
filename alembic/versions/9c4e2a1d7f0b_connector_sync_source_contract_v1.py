"""connector sync source contract v1

Revision ID: 9c4e2a1d7f0b
Revises: 5b3a2f6e1c9d
Create Date: 2026-04-05 00:00:00.000000
"""


from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c4e2a1d7f0b"
down_revision = "5b3a2f6e1c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connector_sync_states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_kind", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("source_json", sa.JSON(), nullable=True))

    connector_sync_states = sa.table(
        "connector_sync_states",
        sa.column("id", sa.Uuid()),
        sa.column("resource_name", sa.String(length=255)),
        sa.column("source_key", sa.String(length=255)),
        sa.column("source_kind", sa.String(length=32)),
        sa.column("source_json", sa.JSON()),
    )
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.select(
                connector_sync_states.c.id,
                connector_sync_states.c.resource_name,
            )
        )
    )
    for row in rows:
        resource_name = str(row.resource_name or "").strip()
        bind.execute(
            connector_sync_states.update()
            .where(connector_sync_states.c.id == row.id)
            .values(
                source_key=resource_name,
                source_kind=("api" if resource_name else None),
                source_json=({"resource": resource_name} if resource_name else {}),
            )
        )

    with op.batch_alter_table("connector_sync_states", schema=None) as batch_op:
        batch_op.alter_column(
            "source_key",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            "source_json",
            existing_type=sa.JSON(),
            nullable=False,
        )
        batch_op.drop_index("ix_connector_sync_states_workspace_resource")
        batch_op.drop_constraint(
            "uq_connector_sync_states_workspace_connection_resource",
            type_="unique",
        )
        batch_op.create_index(
            "ix_connector_sync_states_workspace_source",
            ["workspace_id", "source_key"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_connector_sync_states_workspace_connection_source",
            ["workspace_id", "connection_id", "source_key"],
        )
        batch_op.drop_column("resource_name")


def downgrade() -> None:
    with op.batch_alter_table("connector_sync_states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("resource_name", sa.String(length=255), nullable=True))

    connector_sync_states = sa.table(
        "connector_sync_states",
        sa.column("id", sa.Uuid()),
        sa.column("resource_name", sa.String(length=255)),
        sa.column("source_key", sa.String(length=255)),
        sa.column("source_json", sa.JSON()),
    )
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.select(
                connector_sync_states.c.id,
                connector_sync_states.c.source_key,
                connector_sync_states.c.source_json,
            )
        )
    )
    for row in rows:
        source_json = row.source_json or {}
        resource_name = str(source_json.get("resource") or row.source_key or "").strip()
        bind.execute(
            connector_sync_states.update()
            .where(connector_sync_states.c.id == row.id)
            .values(resource_name=resource_name)
        )

    with op.batch_alter_table("connector_sync_states", schema=None) as batch_op:
        batch_op.alter_column(
            "resource_name",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.drop_index("ix_connector_sync_states_workspace_source")
        batch_op.drop_constraint(
            "uq_connector_sync_states_workspace_connection_source",
            type_="unique",
        )
        batch_op.create_index(
            "ix_connector_sync_states_workspace_resource",
            ["workspace_id", "resource_name"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_connector_sync_states_workspace_connection_resource",
            ["workspace_id", "connection_id", "resource_name"],
        )
        batch_op.drop_column("source_json")
        batch_op.drop_column("source_kind")
        batch_op.drop_column("source_key")
