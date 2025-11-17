from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .base import _Base

class AgentDefinitionBase(_Base):
    name: str = Field(..., description="Name of the agent")
    description: Optional[str] = Field(
        default=None, description="Description of the agent"
    )
    llm_connection_id: UUID = Field(..., description="Associated LLM connection ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the agent was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the agent was last updated",
    )
    definition: str = Field(..., description="Definition or configuration of the agent")

    model_config = ConfigDict(from_attributes=True)
    
class AgentDefinitionCreate(AgentDefinitionBase):
    pass

class AgentDefinitionUpdate(BaseModel):
    id: UUID
    name: Optional[str] = Field(None, description="Name of the agent")
    description: Optional[str] = Field(
        default=None, description="Description of the agent"
    )
    definition: Optional[str] = Field(None, description="Definition or configuration of the agent")
    
class AgentDefinitionResponse(AgentDefinitionBase):
    id: UUID