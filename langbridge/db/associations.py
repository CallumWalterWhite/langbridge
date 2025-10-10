from sqlalchemy import Table, Column, ForeignKey, Boolean, UUID, text
from .base import Base

organization_connectors = Table(
    "organization_connectors",
    Base.metadata,
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True),
    Column("connector_id", UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True),
    # if you do NOT need this flag, remove it (secondary tables normally have only FKs)
    Column("by_project_association", Boolean, nullable=False, server_default=text("false")),
)

project_connectors = Table(
    "project_connectors",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True),
    Column("connector_id", UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True),
)

organization_llm_connections = Table(
    "organization_llm_connections",
    Base.metadata,
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True),
    Column("llm_connection_id", UUID(as_uuid=True), ForeignKey("llm_connections.id"), primary_key=True),
)

project_llm_connections = Table(
    "project_llm_connections",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True),
    Column("llm_connection_id", UUID(as_uuid=True), ForeignKey("llm_connections.id"), primary_key=True),
)