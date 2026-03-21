from __future__ import annotations

from enum import Enum
from typing import Type

from pydantic import ConfigDict

from langbridge.contracts.base import _Base

_PAYLOAD_REGISTRY: dict[str, Type["BaseMessagePayload"]] = {}


class MessageType(str, Enum):
    AGENT_JOB_REQUEST = "agent_job_request"
    AGENTIC_SEMANTIC_MODEL_JOB_REQUEST = "agentic_semantic_model_job_request"
    CONNECTOR_SYNC_JOB_REQUEST = "connector_sync_job_request"
    DATASET_JOB_REQUEST = "dataset_job_request"
    JOB_EVENT = "job_event"
    SEMANTIC_QUERY_REQUEST = "semantic_query_request"
    SQL_JOB_REQUEST = "sql_job_request"


class BaseMessagePayload(_Base):
    model_config = ConfigDict(
        alias_generator=_Base.model_config.get("alias_generator"),
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )


def register_payload(message_type: str):
    def _decorator(payload_model: Type[BaseMessagePayload]) -> Type[BaseMessagePayload]:
        _PAYLOAD_REGISTRY[str(message_type)] = payload_model
        return payload_model

    return _decorator


def resolve_payload_model(message_type: MessageType | str) -> Type[BaseMessagePayload] | None:
    key = message_type.value if isinstance(message_type, MessageType) else str(message_type)
    return _PAYLOAD_REGISTRY.get(key)


__all__ = [
    "BaseMessagePayload",
    "MessageType",
    "register_payload",
    "resolve_payload_model",
]
