from fastapi import Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.orm import Session, sessionmaker
from dependency_injector.wiring import Provide
from ioc import Container
from errors.application_errors import BusinessValidationError
import logging

class UnitOfWorkMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, 
                 session: Session = Depends(Provide[Container.session])):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.session = session

    async def dispatch(self, request: Request, call_next) -> Response:
        self.session.autoflush = False
        try:
            self.session.begin_nested()
            self.logger.debug("Starting a new database session.")
            response = await call_next(request)
            self.session.commit()
            self.session.flush()
            return response
        except Exception as e:
            self.logger.error("Rolling back due to exception: %s", e)
            self.session.rollback()
            raise e
        finally:
            self.session.close()
