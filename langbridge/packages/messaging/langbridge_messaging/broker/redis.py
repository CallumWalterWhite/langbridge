from __future__ import annotations

from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)


class RedisQueue:
    """Simple Redis list-backed queue for message envelopes."""

    def __init__(self, *, url: str | None = None, key: str | None = None) -> None:
        self._url = url or _build_redis_url()
        self._key = key or _default_queue_key()
        self._client = Redis.from_url(self._url, decode_responses=True)

    @property
    def key(self) -> str:
        return self._key

    def ping(self) -> bool:
        return bool(self._client.ping())

    def enqueue(self, message: MessageEnvelope) -> None:
        payload = message.to_json()
        self._client.rpush(self._key, payload)

    def dequeue(self, timeout: int = 1) -> Optional[MessageEnvelope]:
        try:
            result = self._client.blpop(self._key, timeout=timeout)
        except RedisError:
            raise
        if not result:
            return None
        _, raw = result
        return MessageEnvelope.from_json(raw)

    def close(self) -> None:
        try:
            self._client.close()
        except RedisError:
            return


def _build_redis_url() -> str:
    host = settings.REDIS_HOST
    port = settings.REDIS_PORT
    return f"redis://{host}:{port}/0"


def _default_queue_key() -> str:
    channel = settings.REDIS_CHANNEL
    return f"langbridge:queue:{channel}"
