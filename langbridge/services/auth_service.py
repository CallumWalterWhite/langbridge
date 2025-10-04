from __future__ import annotations

from abc import ABC
import base64
import hashlib
import hmac
from typing import List, Literal, Optional, Union

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Request
import httpx

from db.auth import User, OAuthAccount
from errors.application_errors import AuthenticationError, BusinessValidationError
from schemas.base import _Base
from repositories.user_repository import UserRepository, OAuthAccountRepository

GITHUB = Literal['github']
PROVIDERS: List[GITHUB] = ['github']

class OAuthProviderUserInfo(_Base):
    sub: str
    username: str
    name: Optional[str]
    avatar_url: Optional[str]
    email: Optional[str]
    provider: str

class OAuthUserHttpProvider(ABC):
    """Abstract base class for OAuth user info providers."""
    
    async def fetch_user_info(self, request: Request) -> OAuthProviderUserInfo:
        raise NotImplementedError

class GithubUserHttpProvider(OAuthUserHttpProvider):
    """Handles fetching user info from GitHub using OAuth2."""

    def __init__(self, oauth: OAuth):
        self._oauth = oauth

    async def fetch_user_info(self, request: Request) -> OAuthProviderUserInfo:
        async with httpx.AsyncClient() as client:
            user_resp = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token['access_token']}"})
            user_resp.raise_for_status()
            user = user_resp.json()

            email_resp = await client.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {token['access_token']}"})
            email_resp.raise_for_status()
            emails = email_resp.json()

        primary_email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)

        return OAuthProviderUserInfo(
            sub=str(user.get("id")),
            username=user.get("login"),
            name=user.get("name"),
            avatar_url=user.get("avatar_url"),
            email=primary_email,
            provider="github",
        )

class AuthService:
    """Domain logic for authenticating and registering users."""

    __provider_property_map = {
        'github': lambda oauth: oauth.github,  # type: ignore
    }
    __provider_userinfo_map: dict[str, type[OAuthUserHttpProvider]] = {
        'github': GithubUserHttpProvider,
    }

    def __init__(
            self, 
            user_repository: UserRepository,
            oauth: OAuth):
        self._user_repository = user_repository
        self._oauth = oauth

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self._user_repository.get_by_username(username)

    async def authenticate_callback(self, request: Request, provider: Union[GITHUB, None]) -> None:
        if provider not in self.__provider_property_map:
            raise BusinessValidationError(f"Unsupported provider: {provider}")
        try:
            await (
                self.__provider_property_map[provider](self._oauth)
            ).authorize_access_token(request)
        except OAuthError as e:
            raise AuthenticationError(f"OAuth error: {e.error}")

        if provider not in self.__provider_userinfo_map:
            raise BusinessValidationError(f"Unsupported provider for user info: {provider}")
        
        user_info_provider = self.__provider_userinfo_map[provider](self._oauth)
        user_info: OAuthProviderUserInfo = await user_info_provider.fetch_user_info(request)

        user: Optional[User] = self.get_user_by_username(user_info.username)

            
    async def create_user(
            self,
            user_info: OAuthProviderUserInfo,
            oauth_provider: Union[GITHUB, None],
    ):
        if oauth_provider not in PROVIDERS:
            raise BusinessValidationError(f"Unsupported provider: {oauth_provider}")

        if self.get_user_by_username(user_info.username):
            raise BusinessValidationError(f"User with username '{user_info.username}' already exists")

        user = User(
            username=user_info.username,
        )
        self._user_repository.add(user)

        oauth_account = OAuthAccount(
            user=user,
            provider=oauth_provider,
            provider_account_id=user_info.sub,
            access_token="",  # Access token handling can be implemented as needed
        )
        oauth_repo = OAuthAccountRepository(self._user_repository._session)
        oauth_repo.add(oauth_account)

        return user