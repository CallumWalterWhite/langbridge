from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)


@dataclass(frozen=True)
class MessageReceipt:
    stream: str
    group: str
    consumer: str
    entry_id: str


@dataclass(frozen=True)
class ReceivedMessage:
    envelope: MessageEnvelope
    receipt: MessageReceipt


class MessageBroker(Protocol):
    async def publish(self, message: MessageEnvelope, stream: str | None) -> str: ...

    async def consume(self, *, timeout_ms: int, count: int) -> Sequence[ReceivedMessage]: ...

    async def ack(self, message: ReceivedMessage) -> None: ...

    async def nack(self, message: ReceivedMessage, *, error: str | None = None) -> None: ...
