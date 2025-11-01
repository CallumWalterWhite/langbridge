from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import Provide, inject
from ioc import Container
import logging


class UnitOfWorkMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)

    @inject
    async def dispatch(
        self,
        request: Request,
        call_next,
        session: AsyncSession = Provide[Container.async_session],
    ) -> Response:
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
