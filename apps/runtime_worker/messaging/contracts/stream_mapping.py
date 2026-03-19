from __future__ import annotations

from .base import MessageType
from ..broker.redis import RedisStreams

STREAM_MAPPING = {
    MessageType.AGENT_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.AGENTIC_SEMANTIC_MODEL_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.CONNECTOR_SYNC_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.DATASET_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.SEMANTIC_QUERY_REQUEST: RedisStreams.WORKER,
    MessageType.SQL_JOB_REQUEST: RedisStreams.WORKER,
    MessageType.JOB_EVENT: RedisStreams.API,
}

__all__ = ["STREAM_MAPPING"]
