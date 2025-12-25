"""Pydantic models for agent definitions.

These capture the richer contract used by the orchestrator when loading an
agent. The shape is inspired by Snowflake Cortex agent builder concepts: prompt
contract, memory strategy, tools/connectors, access policy, runtime behavior,
output schema, guardrails, and observability knobs.
"""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryStrategy(str, Enum):
    none = "none"
    transient = "transient"
    conversation = "conversation"
    long_term = "long_term"
    vector = "vector"
    database = "database"


class ExecutionMode(str, Enum):
    single_step = "single_step"
    iterative = "iterative"


class OutputFormat(str, Enum):
    text = "text"
    markdown = "markdown"
    json = "json"
    yaml = "yaml"
    
class PromptContract(BaseModel):
    system_prompt: str = Field(..., description="Primary system prompt/instruction.")
    user_instructions: Optional[str] = Field(
        None, description="Additional guidance for how to interpret user input."
    )
    style_guidance: Optional[str] = Field(
        None, description="Tone, persona, and response style expectations."
    )


class MemoryConfig(BaseModel):
    strategy: MemoryStrategy = Field(..., description="How the agent persists/retrieves memory.")
    ttl_seconds: Optional[int] = Field(
        None, description="If transient, how long to keep memory entries (seconds)."
    )
    vector_index: Optional[str] = Field(
        None, description="Vector index name or identifier when using vector memory."
    )
    database_table: Optional[str] = Field(
        None, description="Table or collection for database-backed memory."
    )


class ToolBinding(BaseModel):
    name: str = Field(..., description="Registered tool/connector name.")
    connector_id: Optional[uuid.UUID] = Field(
        None, description="Connector identifier if this tool maps to a connector."
    )
    description: Optional[str] = Field(None, description="Short description of the tool.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific configuration.")


class DataAccessPolicy(BaseModel):
    allowed_connectors: List[uuid.UUID] = Field(
        default_factory=list, description="Connector IDs the agent may access."
    )
    denied_connectors: List[uuid.UUID] = Field(
        default_factory=list, description="Connector IDs explicitly blocked."
    )
    pii_handling: Optional[str] = Field(
        None, description="Notes on how PII is handled/redacted in outputs."
    )
    row_level_filter: Optional[str] = Field(
        None, description="SQL predicate or policy statement for row-level filtering."
    )


class ExecutionBehavior(BaseModel):
    mode: ExecutionMode = Field(..., description="Single response or iterative planning/execution.")
    max_iterations: int = Field(3, description="Cap iterations when in iterative mode.")
    max_steps_per_iteration: int = Field(5, description="Max tool calls per iteration.")
    allow_parallel_tools: bool = Field(False, description="Allow running multiple tools concurrently.")


class OutputSchema(BaseModel):
    format: OutputFormat = Field(..., description="Desired output format.")
    json_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema to validate structured outputs when format=json."
    )
    markdown_template: Optional[str] = Field(
        None, description="Template for markdown rendering, if applicable."
    )


class GuardrailConfig(BaseModel):
    moderation_enabled: bool = Field(True, description="Run outputs through moderation.")
    blocked_categories: List[str] = Field(
        default_factory=list, description="Content categories to block (e.g., violence, hate)."
    )
    regex_denylist: List[str] = Field(
        default_factory=list, description="Regex patterns that should not appear in outputs."
    )
    escalation_message: Optional[str] = Field(
        None, description="What to return when content is blocked."
    )


class ObservabilityConfig(BaseModel):
    emit_traces: bool = Field(True, description="Enable tracing/telemetry for this agent.")
    capture_prompts: bool = Field(True, description="Persist prompts/responses for debugging.")
    audit_fields: List[str] = Field(
        default_factory=list,
        description="Optional list of fields to include in audit logs (e.g., user_id, project_id).",
    )


class AgentDefinitionModel(BaseModel):
    """Complete agent definition payload stored alongside the Agent record."""

    prompt: PromptContract
    memory: MemoryConfig
    tools: List[ToolBinding] = Field(default_factory=list)
    access_policy: DataAccessPolicy
    execution: ExecutionBehavior
    output: OutputSchema
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    model_config = ConfigDict(extra="ignore")
