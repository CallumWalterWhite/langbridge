import enum
from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON, Enum as SqlEnum, UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from db.associations import organization_llm_connections, project_llm_connections
from db.auth import Organization, Project
from .base import Base

class LLMProvider(enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    openai = "openai"  # for backward compatibility

class LLMConnection(Base):
    """SQLAlchemy model for LLM connection configurations"""
    __tablename__ = 'llm_connections'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(1024))
    provider = Column(String(50), nullable=False)  # e.g., 'openai', 'anthropic', etc.
    api_key = Column(String(255), nullable=False) # encrypted in production
    model = Column(String(50))  # e.g., 'gpt-4', 'claude-3', etc.
    configuration = Column(JSON) 
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

    # Relationship with agents
    # agents = relationship("Agent", back_populates="llm_connection")

    # backrefs to orgs/projects
    organizations: Mapped[list["Organization"]] = relationship(
        "Organization", secondary=organization_llm_connections, back_populates="llm_connections"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project", secondary=project_llm_connections, back_populates="llm_connections"
    )

    def __repr__(self):
        return f"<LLMConnection(name='{self.name}', provider='{self.provider}')>"

class AgentDefinition(Base):
    """SQLAlchemy model for AI agents"""
    __tablename__ = 'agents'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    connection_id = Column(Integer, ForeignKey('llm_connections.id'), nullable=False)
    definition = Column(JSON) 
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())