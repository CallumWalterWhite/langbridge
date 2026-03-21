from __future__ import annotations

from typing import Any

from langbridge.runtime.models import RuntimeAgentDefinition
from langbridge.runtime.persistence.db.agent import AgentDefinition


def from_agent_definition_record(value: Any | None) -> RuntimeAgentDefinition | None:
    if value is None:
        return None
    if isinstance(value, RuntimeAgentDefinition):
        return value
    return RuntimeAgentDefinition(
        id=getattr(value, "id"),
        name=str(getattr(value, "name")),
        description=getattr(value, "description", None),
        llm_connection_id=getattr(value, "llm_connection_id"),
        definition=dict(getattr(value, "definition", None) or {}),
        is_active=bool(getattr(value, "is_active", True)),
        created_at=getattr(value, "created_at", None),
        updated_at=getattr(value, "updated_at", None),
    )


def to_agent_definition_record(
    value: RuntimeAgentDefinition | AgentDefinition,
) -> AgentDefinition:
    if isinstance(value, AgentDefinition):
        return value
    return AgentDefinition(
        id=value.id,
        name=value.name,
        description=value.description,
        llm_connection_id=value.llm_connection_id,
        definition=dict(value.definition or {}),
        is_active=value.is_active,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


__all__ = ["from_agent_definition_record", "to_agent_definition_record"]
