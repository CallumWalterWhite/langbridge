import logging
from dependency_injector import providers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ioc import Container


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
        session_factory: async_sessionmaker[AsyncSession] = container.async_session_factory()
        session: AsyncSession = session_factory()

        with container.async_session.override(providers.Object(session)):
            try:
                self.logger.debug("UnitOfWork: starting async DB session")
                response = await call_next(request)
                await session.commit()
                return response
            except Exception as exc:
                self.logger.error("UnitOfWork: rolling back due to exception: %s", exc)
                await session.rollback()
                raise
            finally:
                await session.close()
