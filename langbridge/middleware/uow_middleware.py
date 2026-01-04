import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ioc import Container
from db.session_context import reset_session, set_session


class UnitOfWorkMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        container: Container = request.app.state.container  # type: ignore[attr-defined]
        session_factory = container.async_session_factory()
        session = session_factory()
        token = set_session(session)
        try:
            self.logger.debug("UnitOfWork: starting async DB session")
            response = await call_next(request)
            if response.status_code >= 400:
                await session.rollback()
            else:
                await session.commit()
            return response
        except BaseException as exc:
            self.logger.error("UnitOfWork: rolling back due to exception: %s", exc)
            await session.rollback()
            raise
        finally:
            reset_session(token)
            await session.close()
