
from fastapi import HTTPException, Request, status
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from dependency_injector.wiring import Provide, inject
from ioc import Container
from config import settings
import logging
from auth.jwt import verify_jwt
from models.auth import UserResponse
from services.auth_service import AuthService

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)

    @inject
    async def dispatch(
        self,
        request: Request,
        call_next,
        auth_service: AuthService = Provide[Container.auth_service],
    ) -> Response:
        self.logger.debug(f"AuthMiddleware: Processing request {request.method} {request.url.path}")
        
        if settings.IS_LOCAL:
            self.logger.debug("AuthMiddleware: Skipping auth for local environment")
            token = request.headers.get("Authorization")
            if token == settings.LOCAL_TOKEN:
                self.logger.debug("AuthMiddleware: Local token matched, setting test user")
                request.state.username = "callumwalterwhite"
                request.state.user = await auth_service.get_user_by_username("callumwalterwhite")
                return await call_next(request)
        
        if any(request.url.path.startswith(path) for path in PATHS_TO_EXCLUDE):
            return await call_next(request)

        token = request.cookies.get(settings.COOKIE_NAME)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")

        try:
            claims = verify_jwt(token)
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

        username = claims.get("username") if isinstance(claims, dict) else None
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session payload")

        request.state.username = username
        user: UserResponse = await auth_service.get_user_by_username(username)
        request.state.user = user
        return await call_next(request)
