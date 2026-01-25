from typing import Protocol, Sequence
from ..contracts import (
    MessageType,
    MessageEnvelope as ReturnedMessageEnvelope,
    BaseMessagePayload,
)

class BaseMessageHandler(Protocol):
    message_type: MessageType

    async def handle(self, payload: BaseMessagePayload) -> Sequence[ReturnedMessageEnvelope] | None:
        ...


