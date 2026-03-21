from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from langbridge.contracts.base import _Base

from ..contracts.messages import MessageEnvelope


class MessageReceipt(_Base):
    stream: str
    group: str
    consumer: str
    entry_id: str


class ReceivedMessage(_Base):
    envelope: MessageEnvelope
    receipt: MessageReceipt


class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, message: MessageEnvelope, stream: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def consume(self, *, timeout_ms: int = 1000, count: int = 1) -> Sequence[ReceivedMessage]:
        raise NotImplementedError

    @abstractmethod
    async def ack(self, message: ReceivedMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    async def nack(self, message: ReceivedMessage, *, error: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


__all__ = ["MessageBroker", "MessageReceipt", "ReceivedMessage"]
