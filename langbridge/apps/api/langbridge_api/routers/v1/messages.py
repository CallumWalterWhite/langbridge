from fastapi import APIRouter, HTTPException, Depends, Body, Query, Request, status
from pydantic import ValidationError
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from dependency_injector.wiring import Provide, inject

from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.apps.api.langbridge_api.auth.dependencies import require_internal_service
from langbridge.packages.messaging.langbridge_messaging.flusher.flusher import MessageFlusher

router = APIRouter(prefix="/messages", tags=["messages"])


class PublishCorrelationIdRequest(BaseModel):
    correlation_id: str = Field(..., description="The correlation ID of the messages to publish.")


class PublishCorrelationIdResponse(BaseModel):
    published_count: int = Field(..., description="The number of messages published.")
    
    
@router.post(
    "/publish_by_correlation_id",
    response_model=PublishCorrelationIdResponse,
    status_code=status.HTTP_200_OK,
    # dependencies=[Depends(require_internal_service)],
)
@inject
async def publish_messages_by_correlation_id(
    request: PublishCorrelationIdRequest,
    flusher: MessageFlusher = Depends(Provide[Container.message_flusher]),
):
    """
    Publish all messages with the given correlation ID.
    """
    try:
        published_ids = await flusher.flush_messages_by_correlation_id(
            correlation_id=request.correlation_id
        )
        published_count = len(published_ids)
        return PublishCorrelationIdResponse(published_count=published_count)
    except RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
