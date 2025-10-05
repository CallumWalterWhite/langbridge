from __future__ import annotations

from abc import ABC
from typing import List, Literal, Optional, Union
import uuid

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Request
import httpx

from db.auth import User, OAuthAccount
from errors.application_errors import AuthenticationError, BusinessValidationError
from schemas.base import _Base
from repositories.user_repository import UserRepository, OAuthAccountRepository
from services.organization_service import OrganizationService

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

    async def fetch_user_info(self, token: dict) -> OAuthProviderUserInfo:
        raise NotImplementedError


class GithubUserHttpProvider(OAuthUserHttpProvider):
    """Handles fetching user info from GitHub using OAuth2."""

    def __init__(self, oauth: OAuth):
        self._oauth = oauth

    async def fetch_user_info(self, token: dict) -> OAuthProviderUserInfo:
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            user_resp.raise_for_status()
            user = user_resp.json()

            email_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
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
        'github': lambda oauth: oauth.github,  # type: ignore[attr-defined]
    }
    __provider_userinfo_map: dict[str, type[OAuthUserHttpProvider]] = {
        'github': GithubUserHttpProvider,
    }

    def __init__(
        self,
        user_repository: UserRepository,
        oauth_account_repository: OAuthAccountRepository,
        organization_service: OrganizationService,
        oauth: OAuth,
    ) -> None:
        self._user_repository = user_repository
        self._oauth_account_repository = oauth_account_repository
        self._organization_service = organization_service
        self._oauth = oauth

    def get_user_by_username(self, username: str) -> User:
        user = self._user_repository.get_by_username(username)
        if not user:
            raise RecursionError("User not found")
        return user

    async def authorize_redirect(
        self,
        request: Request,
        provider: Union[GITHUB, None],
        redirect_uri: str,
    ) -> httpx.Response:
        if provider not in self.__provider_property_map:
            raise BusinessValidationError(f"Unsupported provider: {provider}")
        oauth_provider = self.__provider_property_map[provider](self._oauth)
        return await oauth_provider.authorize_redirect(request, redirect_uri)  # type: ignore[attr-defined]

    async def authenticate_callback(
        self,
        request: Request,
        provider: Union[GITHUB, None],
    ) -> User:
        if provider not in self.__provider_property_map:
            raise BusinessValidationError(f"Unsupported provider: {provider}")
        try:
            token = await (
                self.__provider_property_map[provider](self._oauth)
            ).authorize_access_token(request)
        except OAuthError as exc:
            raise AuthenticationError(f"OAuth error: {exc.error}")

        if provider not in self.__provider_userinfo_map:
            raise BusinessValidationError(f"Unsupported provider for user info: {provider}")

        user_info_provider = self.__provider_userinfo_map[provider](self._oauth) # type: ignore[arg-type]
        user_info: OAuthProviderUserInfo = await user_info_provider.fetch_user_info(token)

        user: Optional[User] = self._user_repository.get_by_username(user_info.username)

        if not user:
            user = self.create_user(user_info, provider)
        elif not (
            user.oauth_accounts
            and any(
                oa.provider == provider and oa.provider_account_id == user_info.sub
                for oa in user.oauth_accounts
            )
        ):
            self.create_oauth_account(user, user_info, provider)

        self._organization_service.ensure_default_workspace_for_user(user)
        return user

    def create_oauth_account(
        self,
        user: User,
        user_info: OAuthProviderUserInfo,
        oauth_provider: Union[GITHUB, None],
    ) -> OAuthAccount:
        if oauth_provider not in PROVIDERS:
            raise BusinessValidationError(f"Unsupported provider: {oauth_provider}")

        oauth_account = OAuthAccount(
            id=uuid.uuid4(),
            user=user,
            provider=oauth_provider,
            provider_account_id=user_info.sub,
            name=user_info.name,
            email=user_info.email,
            avatar_url=user_info.avatar_url,
            sub=user_info.sub,
        )
        self._oauth_account_repository.add(oauth_account)

        return oauth_account

    def create_user(
        self,
        user_info: OAuthProviderUserInfo,
        oauth_provider: Union[GITHUB, None],
    ) -> User:
        if oauth_provider not in PROVIDERS:
            raise BusinessValidationError(f"Unsupported provider: {oauth_provider}")

        if self._user_repository.get_by_username(user_info.username):
            raise BusinessValidationError(
                f"User with username '{user_info.username}' already exists"
            )

        user = User(
            id=uuid.uuid4(),
            username=user_info.username,
        )
        self._user_repository.add(user)
        self.create_oauth_account(user, user_info, oauth_provider)
        return user
