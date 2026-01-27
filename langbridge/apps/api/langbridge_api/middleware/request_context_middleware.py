import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from langbridge.apps.api.langbridge_api.request_context import (
    RequestContext,
    reset_request_context,
    set_request_context,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request-scoped context object to the current request."""

    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        ctx = RequestContext()
        request.state.request_context = ctx
        token = set_request_context(ctx)
        try:
            return await call_next(request)
        finally:
            reset_request_context(token)
