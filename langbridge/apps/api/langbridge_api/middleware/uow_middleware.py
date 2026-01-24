import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from langbridge.apps.api.langbridge_api.ioc import Container
from langbridge.apps.api.langbridge_api.db.session_context import reset_session, set_session


class UnitOfWorkMiddleware(BaseHTTPMiddleware):
    """
    Middleware that manages a database session for each request.
    It commits the session if the request completes successfully (status code < 400),
    and rolls back otherwise.
    """
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Assuming the DI container is attached to app.state
        container: Container = request.app.state.container  # type: ignore[attr-defined]
        
        session_factory = container.async_session_factory()
        session = session_factory()
        token = set_session(session)
        
        try:
            self.logger.debug("UnitOfWork: starting async DB session")
            response = await call_next(request)
            
            if response.status_code >= 400:
                self.logger.debug(f"UnitOfWork: rolling back due to status code {response.status_code}")
                await session.rollback()
            else:
                self.logger.debug("UnitOfWork: committing session")
                await session.commit()
                
            return response
            
        except BaseException as exc:
            self.logger.error("UnitOfWork: rolling back due to exception: %s", exc)
            await session.rollback()
            raise
            
        finally:
            reset_session(token)
            await session.close()
            self.logger.debug("UnitOfWork: session closed")
