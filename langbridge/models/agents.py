import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .base import _Base
from orchestrator.definitions import AgentDefinitionModel

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
    definition: AgentDefinitionModel = Field(
        ..., description="Definition or configuration of the agent"
    )
    is_active: bool = Field(default=True, description="Whether the agent is active")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("definition", mode="before")
    @classmethod
    def _parse_definition(cls, value: Any) -> Any:
        if isinstance(value, AgentDefinitionModel):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("definition must be valid JSON") from exc
        return value
    
class AgentDefinitionCreate(AgentDefinitionBase):
    pass

class AgentDefinitionUpdate(_Base):
    name: Optional[str] = Field(None, description="Name of the agent")
    description: Optional[str] = Field(
        default=None, description="Description of the agent"
    )
    llm_connection_id: Optional[UUID] = Field(
        None, description="Associated LLM connection ID"
    )
    definition: Optional[AgentDefinitionModel] = Field(
        None, description="Definition or configuration of the agent"
    )
    is_active: Optional[bool] = Field(None, description="Whether the agent is active")

    @field_validator("definition", mode="before")
    @classmethod
    def _parse_definition(cls, value: Any) -> Any:
        if value is None or isinstance(value, AgentDefinitionModel):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("definition must be valid JSON") from exc
        return value
    
class AgentDefinitionResponse(AgentDefinitionBase):
    id: UUID