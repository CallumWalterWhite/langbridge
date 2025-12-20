import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from errors.application_errors import (
    AuthenticationError,
    AuthorizationError,
    ResourceAlreadyExists, 
    ResourceNotFound, 
    InvalidRequest, 
    ApplicationError,
    BusinessValidationError
)

class ErrorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.ERROR)

    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
        except ResourceAlreadyExists as e:
            self.logger.error("Resource already exists", exc_info=True)
            response = Response(content=str(e), status_code=409)
        except ResourceNotFound as e:
            self.logger.error("Resource not found", exc_info=True)
            response = Response(content=str(e), status_code=404)
        except InvalidRequest as e:
            self.logger.error("Invalid request", exc_info=True)
            response = Response(content=str(e), status_code=400)
        except ApplicationError as e:
            self.logger.error("Application error", exc_info=True)
            response = Response(content=str(e), status_code=500)
        except BusinessValidationError as e:
            self.logger.error("Business validation error", exc_info=True)
            response = Response(content=str(e), status_code=400)
        except AuthenticationError as e:
            self.logger.error("Authentication error", exc_info=True)
            response = Response(content=str(e), status_code=401)
        except AuthorizationError as e:
            self.logger.error("Authorization error", exc_info=True)
            response = Response(content=str(e), status_code=403)
        except Exception as e:
            self.logger.error("Unknown error", exc_info=True)
            response = Response(content=str(e), status_code=500)
        
        return response