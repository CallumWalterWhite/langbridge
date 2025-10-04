from sqlalchemy import UUID, Column, String
from db.base import Base

class Connector(Base):
    """Base connector entity stored in the relational database."""

    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False)
    config = Column(String, nullable=False)  # JSON or other serialized config
    
class DatabaseConnector(Connector):
    """Database connector entity stored in the relational database."""

    __tablename__ = "database_connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    database_name = Column(String(255), nullable=False)
    
class APIConnector(Connector):
    """API connector entity stored in the relational database."""

    __tablename__ = "api_connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)