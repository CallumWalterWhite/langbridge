from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from langbridge.packages.messaging.langbridge_messaging.broker.redis import RedisBroker
from langbridge.packages.messaging.langbridge_messaging.contracts.base import (
    TestMessagePayload,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.messages import (
    MessageEnvelope,
    MessageType,
)

router = APIRouter(prefix="/messages", tags=["messages"])


class PublishTestMessageRequest(BaseModel):
    message_type: MessageType = Field(default=MessageType.TEST)
    payload: TestMessagePayload = Field(
        default_factory=lambda: TestMessagePayload(message="hello from api")
    )


class PublishTestMessageResponse(BaseModel):
    id: str
    stream: str
    entry_id: str
    message_type: str


@router.post("/test", response_model=PublishTestMessageResponse)
async def publish_test_message(
    request: PublishTestMessageRequest,
) -> PublishTestMessageResponse:
    broker = RedisBroker()
    envelope = MessageEnvelope(
        message_type=request.message_type,
        payload=request.payload,
    )
    try:
        entry_id = await broker.publish(envelope)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis publish failed: {exc}") from exc
    finally:
        await broker.close()

    return PublishTestMessageResponse(
        id=str(envelope.id),
        stream=broker.stream,
        entry_id=entry_id,
        message_type=envelope.message_type,
    )
