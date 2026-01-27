from enum import Enum
from typing import Callable, TypeVar
from pydantic import BaseModel


class MessageType(str, Enum):
    """Message types."""
    TEST = "test"
    AGENT_JOB_REQUEST = "agent_job_request"

    def __str__(self) -> str:
        return self.value


class BaseMessagePayload(BaseModel):
    """Base class for message payloads."""
    __message_type__: str | None = None
    
    @property
    def message_type(self) -> MessageType:
        message_type = getattr(self, "__message_type__", None)
        if not message_type:
            raise NotImplementedError("Subclasses must define a __message_type__ attribute.")
        return MessageType(message_type)


PayloadT = TypeVar("PayloadT", bound=BaseMessagePayload)

_PAYLOAD_REGISTRY: dict[str, type[BaseMessagePayload]] = {}


def register_payload(message_type: str) -> Callable[[type[PayloadT]], type[PayloadT]]:
    def _decorator(cls: type[PayloadT]) -> type[PayloadT]:
        _PAYLOAD_REGISTRY[message_type] = cls
        cls.__message_type__ = message_type
        return cls

    return _decorator


def get_payload_model(message_type: str) -> type[BaseMessagePayload] | None:
    return _PAYLOAD_REGISTRY.get(message_type)

@register_payload("test")
class TestMessagePayload(BaseMessagePayload):
    message: str
