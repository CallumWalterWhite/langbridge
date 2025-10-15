from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"

class LLMConnectionBase(BaseModel):
    name: str = Field(..., description="Name of the LLM connection")
    provider: LLMProvider = Field(..., description="LLM provider (openai, anthropic, etc.)")
    model: str = Field(..., description="Model name (e.g., gpt-4, claude-3)")
    configuration: Optional[Dict] = Field(default={}, description="Additional provider-specific configuration")
    description: Optional[str] = Field(default=None, description="Description of the LLM connection")
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None

class LLMConnectionCreate(LLMConnectionBase):
    api_key: str = Field(..., description="API key for the LLM provider")

class LLMConnectionUpdate(BaseModel):
    name: str
    api_key: str
    model: str
    configuration: Dict
    is_active: bool
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None

class LLMConnectionResponse(LLMConnectionBase):
    id: UUID
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None

    class Config:
        from_attributes = True

class LLMConnectionTest(BaseModel):
    provider: LLMProvider
    api_key: str
    model: str
    configuration: Optional[Dict] = Field(default={})