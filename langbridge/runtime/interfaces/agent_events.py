"""Compatibility wrapper for agent event protocols."""

from langbridge.runtime.events import AgentEventEmitter as IAgentEventEmitter
from langbridge.runtime.events import AgentEventVisibility

__all__ = ["AgentEventVisibility", "IAgentEventEmitter"]
