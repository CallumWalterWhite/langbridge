import uuid
from sqlalchemy import UUID, Column, String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, relationship
from .base import Base
from .associations import organization_connectors, project_connectors
from .auth import Organization, Project

class Connector(Base):
    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(1024))
    connector_type = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    config_json = Column(String, nullable=False)
    connection_metadata_json = Column(JSON, nullable=True)
    secret_references_json = Column(JSON, nullable=True)
    access_policy_json = Column(JSON, nullable=True)

    # polymorphic
    __mapper_args__ = {"polymorphic_identity": "connector", "polymorphic_on": type}

    # backrefs to orgs/projects
    organizations: Mapped[list["Organization"]] = relationship(
        "Organization", secondary=organization_connectors, back_populates="connectors"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project", secondary=project_connectors, back_populates="connectors"
    )

class DatabaseConnector(Connector):
    __tablename__ = "database_connectors"
    id = Column(UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "database_connector"}

class APIConnector(Connector):
    __tablename__ = "api_connectors"
    id = Column(UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "api_connector"}
