from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from langbridge.packages.messaging.langbridge_messaging.broker.redis_streams import (
    RedisStreamsBroker,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
)

router = APIRouter(prefix="/messages", tags=["messages"])


class PublishTestMessageRequest(BaseModel):
    message_type: str = Field(default="test", min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class PublishTestMessageResponse(BaseModel):
    id: str
    stream: str
    entry_id: str
    message_type: str


@router.post("/test", response_model=PublishTestMessageResponse)
async def publish_test_message(
    request: PublishTestMessageRequest,
) -> PublishTestMessageResponse:
    broker = RedisStreamsBroker()
    envelope = MessageEnvelope(
        message_type=request.message_type,
        payload=request.payload,
    )
    try:
        entry_id = broker.publish(envelope)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis publish failed: {exc}") from exc

    return PublishTestMessageResponse(
        id=str(envelope.id),
        stream=broker.stream,
        entry_id=entry_id,
        message_type=envelope.message_type,
    )
