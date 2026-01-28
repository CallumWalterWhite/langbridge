import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import uuid
from langbridge.apps.api.langbridge_api.ioc import Container
from dependency_injector.wiring import Provide, inject
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
            self.logger.debug(f"MessageFlusherMiddleware: Flushing messages for correlation ID {correlation_id} after request {request.method} {request.url.path}")
            
            if message_flusher.get_message_count_by_correlation_id(correlation_id) == 0:
                self.logger.debug(f"MessageFlusherMiddleware: No pending messages for correlation ID {correlation_id}")
                return response
            
            await internal_api_client.post(
                self.FLUSH_ENDPOINT,
                json={"correlation_id": correlation_id},
            )
        
        return response
