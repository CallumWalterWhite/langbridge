import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import uuid



class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set the correlation ID for messages in the request context.
    """
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = self.__create_correlation_id()
            self.logger.debug(
                "CorrelationIdMiddleware: Created new correlation ID %s for request %s %s",
                correlation_id,
                request.method,
                request.url.path,
            )
        else:
            self.logger.debug(
                "CorrelationIdMiddleware: Set correlation ID %s for request %s %s",
                correlation_id,
                request.method,
                request.url.path,
            )

        request.state.correlation_id = correlation_id
        if hasattr(request.state, "request_context"):
            request.state.request_context.correlation_id = correlation_id

        response = await call_next(request)

        self.logger.debug(
            "CorrelationIdMiddleware: Reset correlation ID after request %s %s",
            request.method,
            request.url.path,
        )

        return response
    
    def __create_correlation_id(self) -> str:
        return str(uuid.uuid4())
