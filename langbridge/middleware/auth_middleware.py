
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.orm import Session
from dependency_injector.wiring import Provide
from ioc import Container
from config import settings
import logging
from auth.jwt import verify_jwt
from services.auth_service import AuthService

PATHS_TO_EXCLUDE = [
    "/api/v1/auth/health",
    "/api/v1/auth/login",
    "/api/v1/auth/github/callback",
    "/api/v1/auth/google/callback",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/docs",
    "/openapi.json",
]

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, 
                 auth_service: AuthService = Depends(Provide[Container.auth_service]),):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.auth_service = auth_service

    async def dispatch(self, request: Request, call_next) -> Response:
        self.logger.debug(f"AuthMiddleware: Processing request {request.method} {request.url.path}")
        
        if settings.IS_LOCAL:
            token = request.headers.get("Authorization")
            if token == settings.LOCAL_TOKEN:
                request.state.username = "CallumWalterWhite"
                request.state.user = self.auth_service.get_user_by_username("CallumWalterWhite")
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
        user = self.auth_service.get_user_by_username(username)
        request.state.user = user
        return await call_next(request)
