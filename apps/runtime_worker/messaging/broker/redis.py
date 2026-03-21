from __future__ import annotations

import uuid
from enum import Enum
from typing import Sequence

from langbridge.config import settings

from .base import MessageBroker, ReceivedMessage
from ..contracts.messages import MessageEnvelope


class RedisStreams(str, Enum):
    WORKER = settings.REDIS_WORKER_STREAM
    API = settings.REDIS_API_STREAM
    DEAD_LETTER = settings.REDIS_DEAD_LETTER_STREAM


class RedisBroker(MessageBroker):
    def __init__(self, *, stream: str, group: str) -> None:
        self.stream = stream
        self.group = group

    async def publish(self, message: MessageEnvelope, stream: str | None = None) -> str:
        return str(uuid.uuid4())

    async def consume(self, *, timeout_ms: int = 1000, count: int = 1) -> Sequence[ReceivedMessage]:
        return []

    async def ack(self, message: ReceivedMessage) -> None:
        return None

    async def nack(self, message: ReceivedMessage, *, error: str | None = None) -> None:
        return None

    async def close(self) -> None:
        return None


__all__ = ["RedisBroker", "RedisStreams"]
