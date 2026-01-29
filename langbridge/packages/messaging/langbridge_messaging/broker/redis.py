from __future__ import annotations

import asyncio
from enum import Enum
import inspect
import json
import os
import socket
from typing import Any, Sequence

from redis.asyncio import Redis
from redis.exceptions import ResponseError, RedisError

from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.messaging.langbridge_messaging.broker.base import (
    MessageBroker,
    MessageReceipt,
    ReceivedMessage,
)
from pydantic import ValidationError

from langbridge.packages.messaging.langbridge_messaging.contracts.base import (
    MessageType,
    TestMessagePayload,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)

class RedisStreams(str, Enum):
    """Predefined Redis Streams for LangBridge."""

    WORKER = "langbridge:worker_stream"
    DEAD_LETTER = "langbridge:dead_letter_stream"
    API = "langbridge:api_stream"

class RedisBroker(MessageBroker):
    """Redis Streams broker with consumer group semantics."""

    def __init__(
        self,
        *,
        url: str | None = None,
        stream: RedisStreams | None = None,
        group: str | None = None,
        consumer: str | None = None,
        dead_letter_stream: str | None = None,
        max_attempts: int = 5,
    ) -> None:
        self._url = url or _build_redis_url()
        self._stream = stream or _default_stream()
        self._group = group or _default_group()
        self._consumer = consumer or _default_consumer()
        self._dead_letter_stream = dead_letter_stream or _default_dead_letter_stream()
        self._max_attempts = max_attempts
        self._client = Redis.from_url(self._url, decode_responses=True)
        self._group_ready = False
        self._group_lock = asyncio.Lock()

    @property
    def stream(self) -> str:
        return self._stream

    @property
    def group(self) -> str:
        return self._group

    @property
    def consumer(self) -> str:
        return self._consumer

    @property
    def dead_letter_stream(self) -> str:
        return self._dead_letter_stream

    async def ping(self) -> bool:
        return bool(await _maybe_await(self._client.ping()))

    async def publish(self, message: MessageEnvelope, stream: RedisStreams | None) -> str:
        await self._ensure_group()
        return await _maybe_await(self._client.xadd(stream.value or self._stream, _encode_message(message)))

    async def consume(
        self, *, timeout_ms: int = 1000, count: int = 1
    ) -> Sequence[ReceivedMessage]:
        await self._ensure_group()
        results = await _maybe_await(
            self._client.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=count,
            block=timeout_ms,
            )
        )
        return _parse_results(results, self._stream, self._group, self._consumer)

    async def ack(self, message: ReceivedMessage) -> None:
        await _maybe_await(
            self._client.xack(
                message.receipt.stream, message.receipt.group, message.receipt.entry_id
            )
        )

    async def nack(self, message: ReceivedMessage, *, error: str | None = None) -> None:
        envelope = message.envelope
        envelope.increment_attempt()
        max_attempts = envelope.headers.max_attempts or self._max_attempts
        if envelope.headers.attempt >= max_attempts:
            await _maybe_await(
                self._client.xadd(
                    self._dead_letter_stream,
                    {
                        "data": envelope.to_json(),
                        "type": envelope.message_type,
                        "error": error or "",
                        "source_stream": message.receipt.stream,
                    },
                )
            )
        else:
            await _maybe_await(self._client.xadd(self._stream, _encode_message(envelope)))
        await self.ack(message)

    async def close(self) -> None:
        try:
            await _maybe_await(self._client.close())
        except RedisError:
            return

    async def reclaim(
        self,
        *,
        min_idle_ms: int = 60000,
        count: int = 10,
        start_id: str = "0-0",
    ) -> Sequence[ReceivedMessage]:
        """
        Reclaim idle messages from other consumers (best-effort).
        Requires Redis 6.2+ for XAUTOCLAIM.
        """
        try:
            next_start, messages = await _maybe_await(
                self._client.xautoclaim(
                    name=self._stream,
                    groupname=self._group,
                    consumername=self._consumer,
                    min_idle_time=min_idle_ms,
                    start_id=start_id,
                    count=count,
                )
            )
        except ResponseError:
            return []
        results = [(self._stream, messages)]
        return _parse_results(results, self._stream, self._group, self._consumer)

    async def _ensure_group(self) -> None:
        if self._group_ready:
            return
        async with self._group_lock:
            if self._group_ready:
                return
            try:
                await _maybe_await(
                    self._client.xgroup_create(
                        name=self._stream,
                        groupname=self._group,
                        id="$",
                        mkstream=True,
                    )
                )
            except ResponseError as exc:
                if "BUSYGROUP" in str(exc):
                    self._group_ready = True
                    return
                raise
            self._group_ready = True


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


def _encode_message(message: MessageEnvelope) -> dict[str, str]:
    return {
        "data": message.to_json(),
        "type": message.message_type,
    }


def _parse_results(
    results: Any, stream: str, group: str, consumer: str
) -> list[ReceivedMessage]:
    if not results:
        return []
    received: list[ReceivedMessage] = []
    for _, entries in results:
        for entry_id, fields in entries:
            envelope = _decode_message(fields)
            receipt = MessageReceipt(
                stream=stream,
                group=group,
                consumer=consumer,
                entry_id=entry_id,
            )
            received.append(ReceivedMessage(envelope=envelope, receipt=receipt))
    return received


def _decode_message(fields: dict[str, str]) -> MessageEnvelope:
    raise ValueError(f"Invalid message payload, missing fields: {fields}")
    if "data" in fields:
        try:
            return MessageEnvelope.from_json(fields["data"])
        except ValidationError as exc:
            raise ValueError("Invalid message payload") from exc
    payload = fields.get("payload")
    message_type = fields.get("type", "unknown")
    if payload:
        try:
            return MessageEnvelope(message_type=message_type, payload=json.loads(payload))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid message in payload {fields}: {exc}") from exc 
    raise ValueError("Invalid message payload")


def _build_redis_url() -> str:
    host = settings.REDIS_HOST
    port = settings.REDIS_PORT
    return f"redis://{host}:{port}/0"


def _default_stream() -> str:
    if settings.REDIS_STREAM:
        return settings.REDIS_STREAM
    return f"langbridge:{settings.REDIS_CHANNEL}"


def _default_group() -> str:
    return settings.REDIS_CONSUMER_GROUP


def _default_consumer() -> str:
    override = settings.REDIS_CONSUMER_NAME
    if override:
        return override
    return os.environ.get("HOSTNAME") or socket.gethostname()


def _default_dead_letter_stream() -> str:
    return settings.REDIS_DEAD_LETTER_STREAM
