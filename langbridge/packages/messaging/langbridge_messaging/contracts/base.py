from typing import Callable, TypeVar

from pydantic import BaseModel


class BaseMessagePayload(BaseModel):
    pass


PayloadT = TypeVar("PayloadT", bound=BaseMessagePayload)

_PAYLOAD_REGISTRY: dict[str, type[BaseMessagePayload]] = {}


def register_payload(message_type: str) -> Callable[[type[PayloadT]], type[PayloadT]]:
    def _decorator(cls: type[PayloadT]) -> type[PayloadT]:
        _PAYLOAD_REGISTRY[message_type] = cls
        return cls

    return _decorator


def get_payload_model(message_type: str) -> type[BaseMessagePayload] | None:
    return _PAYLOAD_REGISTRY.get(message_type)



@register_payload("test")
class TestMessagePayload(BaseMessagePayload):
    message: str
