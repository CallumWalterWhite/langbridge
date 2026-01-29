import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import uuid
from langbridge.apps.api.langbridge_api.ioc import Container
from dependency_injector.wiring import Provide, inject
from langbridge.apps.api.langbridge_api.routers.v1.messages import PublishCorrelationIdRequest
from langbridge.apps.api.langbridge_api.services.internal_api_client import InternalApiClient
from langbridge.apps.api.langbridge_api.db.session_context import reset_session, set_session
from langbridge.packages.messaging.langbridge_messaging.flusher.flusher import MessageFlusher


class MessageFlusherMiddleware(BaseHTTPMiddleware):
    """
    Middleware to flush pending messages after each request.
    """
    
    FLUSH_ENDPOINT = "/api/v1/messages/publish_by_correlation_id"
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
        internal_api_client: InternalApiClient = Provide[Container.internal_api_client],
        message_flusher: MessageFlusher = Provide[Container.message_flusher],
    ) -> Response:
        response = await call_next(request)

        if request.url.path == self.FLUSH_ENDPOINT:
            return response

        correlation_id = getattr(
            getattr(request.state, "request_context", None),
            "correlation_id",
            None,
        )
        if not correlation_id:
            correlation_id = getattr(request.state, "correlation_id", None)
        if correlation_id:
            self.logger.info(f"MessageFlusherMiddleware: Flushing messages for correlation ID {correlation_id} after request {request.method} {request.url.path}")
            
            message_count = await message_flusher.get_message_count_by_correlation_id(correlation_id)
            
            if message_count == 0:
                self.logger.info(f"MessageFlusherMiddleware: No pending messages for correlation ID {correlation_id}")
                return response
            
            self.logger.info(f"MessageFlusherMiddleware: Found {message_count} pending messages for correlation ID {correlation_id}, invoking internal API to flush.")
            
            publish_request: PublishCorrelationIdRequest = PublishCorrelationIdRequest(
                correlation_id=correlation_id
            )
            
            await internal_api_client.post(
                path=self.FLUSH_ENDPOINT,
                json=publish_request.model_dump(mode="json"),
            )
            
        
        return response
