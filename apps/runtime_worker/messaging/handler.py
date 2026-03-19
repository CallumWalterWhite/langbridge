from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from .contracts.messages import MessageEnvelope


class BaseMessageHandler(ABC):
    message_type = None

    @abstractmethod
    async def handle(self, payload):
        raise NotImplementedError

    async def handle_message(self, message: MessageEnvelope) -> Sequence[MessageEnvelope] | None:
        return await self.handle(message.payload)


__all__ = ["BaseMessageHandler"]
