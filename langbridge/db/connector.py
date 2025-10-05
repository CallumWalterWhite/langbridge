from sqlalchemy import UUID, Column, String, ForeignKey
from db.base import Base

class Connector(Base):
    """A Data source Connector."""

    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False)
    config_json = Column(String, nullable=False)  # JSON configuration as a string

    __mapper_args__ = {
        "polymorphic_identity": "connector",   # Base identity
        "polymorphic_on": type                 # Discriminator column
    }


class DatabaseConnector(Connector):
    """A Database Connector."""

    __tablename__ = "database_connectors"

    id = Column(UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "database_connector",
    }


class APIConnector(Connector):
    """An API Connector."""

    __tablename__ = "api_connectors"

    id = Column(UUID(as_uuid=True), ForeignKey("connectors.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "api_connector",
    }
