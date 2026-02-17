from typing import Optional, Protocol

from fastapi.responses import JSONResponse
from langbridge.apps.api.langbridge_api.auth.jwt import verify_jwt
from langbridge.apps.api.langbridge_api.auth.jwt import verify_jwt
from langbridge.apps.api.langbridge_api.services.auth import auth_service
from langbridge.apps.api.langbridge_api.services.auth.auth_service import AuthService
from langbridge.apps.api.langbridge_api.services.auth.token_service import TokenService
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.errors.application_errors import AuthenticationError, JWTError


class AuthenticationProvider(Protocol):
    async def authenticate(self, token: str) -> Optional[UserResponse]:
        ...


class JwtAuthenticationProvider:
    def __init__(self,
                 auth_service: AuthService):
        self.auth_service = auth_service

    async def authenticate(self, token: str) -> UserResponse:
        try:
            claims = verify_jwt(token)
        except JWTError as exc:
            raise AuthenticationError("JWT authentication failed") from exc
        
        if not claims:
            raise AuthenticationError("JWT authentication failed")

        id = claims.get("id") if isinstance(claims, dict) else None
        if not id:
            raise AuthenticationError("JWT authentication failed")
        try:
            user = await self.auth_service.get_user_by_id(id)
        except Exception as exc:
            raise AuthenticationError("JWT authentication failed") from exc
        
        return user


class PatAuthenticationProvider:
    def __init__(self, 
                 auth_service: AuthService,
                 token_service: TokenService):
        self.auth_service = auth_service
        self.token_service = token_service

    async def authenticate(self, token: str) -> UserResponse:
        user = await self.token_service.authenticate_with_pat(token)
        if not user:
            raise AuthenticationError("PAT authentication failed")
        try:
            user = await self.auth_service.get_user_by_id(user.id)
        except Exception as exc:
            raise AuthenticationError("PAT authentication failed") from exc
        
        return user

AUTHORIZATION_HEADER_PREFIX = "Bearer "

class TokenAuthenticationResolver:
    def __init__(self, token_service: TokenService, auth_service: AuthService):
        self.jwt_provider = JwtAuthenticationProvider(auth_service)
        self.pat_provider = PatAuthenticationProvider(auth_service, token_service)

    def resolve(self, token: str) -> AuthenticationProvider:
        if token.startswith(AUTHORIZATION_HEADER_PREFIX):
            return self.jwt_provider
        return self.pat_provider
