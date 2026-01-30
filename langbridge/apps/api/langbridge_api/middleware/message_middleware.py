import logging
from starlette.background import BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from langbridge.apps.api.langbridge_api.ioc import Container
from dependency_injector.wiring import Provide
from langbridge.apps.api.langbridge_api.routers.v1.messages import PublishCorrelationIdRequest
from langbridge.apps.api.langbridge_api.services.internal_api_client import InternalApiClient


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
    ) -> Response:
        response = await call_next(request)

        if request.url.path == self.FLUSH_ENDPOINT:
            return response

        request_context = getattr(request.state, "request_context", None)
        if not request_context or not getattr(request_context, "has_outbox_message", False):
            return response

        correlation_id = getattr(
            request_context,
            "correlation_id",
            None,
        )
        if not correlation_id:
            correlation_id = getattr(request.state, "correlation_id", None)
        if correlation_id:
            self.logger.info(f"MessageFlusherMiddleware: Flushing messages for correlation ID {correlation_id} after request {request.method} {request.url.path}")

            self.logger.info("MessageFlusherMiddleware: Outbox activity detected, invoking internal API to flush.")
            
            publish_request: PublishCorrelationIdRequest = PublishCorrelationIdRequest(
                correlation_id=correlation_id
            )
            
            async def _flush_async() -> None:
                try:
                    await internal_api_client.post(
                        path=self.FLUSH_ENDPOINT,
                        json=publish_request.model_dump(mode="json"),
                    )
                except Exception as exc:
                    self.logger.warning(
                        "MessageFlusherMiddleware: Fire-and-forget flush failed for correlation ID %s: %s",
                        correlation_id,
                        exc,
                    )

            if response.background is None:
                response.background = BackgroundTasks()
            response.background.add_task(_flush_async) # type: ignore
            
        
        return response
