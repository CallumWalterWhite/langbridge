

from abc import ABC
from typing import List, Literal, Optional, Tuple
import uuid
import re

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Request
import httpx

from db.auth import User, OAuthAccount
from errors.application_errors import AuthenticationError, BusinessValidationError
from schemas.base import _Base
from repositories.user_repository import UserRepository, OAuthAccountRepository
from services.organization_service import OrganizationService

ProviderLiteral = Literal['github', 'google']
PROVIDERS: List[ProviderLiteral] = ['github', 'google']


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


class GoogleUserHttpProvider(OAuthUserHttpProvider):
    """Handles fetching user info from Google using OAuth2."""

    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(self, oauth: OAuth):
        self._oauth = oauth

    async def fetch_user_info(self, token: dict) -> OAuthProviderUserInfo:
        access_token = token.get("access_token")
        if not access_token:
            raise AuthenticationError("Missing access token in Google OAuth flow.")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            profile = response.json()

        email = profile.get("email")
        raw_username = ""
        if email:
            raw_username = email.split("@")[0]
        elif profile.get("name"):
            raw_username = profile["name"].replace(" ", "")
        elif profile.get("id"):
            raw_username = profile["id"]

        return OAuthProviderUserInfo(
            sub=str(profile.get("id")),
            username=raw_username,
            name=profile.get("name"),
            avatar_url=profile.get("picture"),
            email=email,
            provider="google",
        )


class AuthService:
    """Domain logic for authenticating and registering users."""

    __provider_property_map = {
        'github': lambda oauth: oauth.github,  # type: ignore[attr-defined]
        'google': lambda oauth: oauth.google,  # type: ignore[attr-defined]
    }
    __provider_userinfo_map: dict[str, type[OAuthUserHttpProvider]] = {
        'github': GithubUserHttpProvider,
        'google': GoogleUserHttpProvider,
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

    async def get_user_by_username(self, username: str) -> User:
        user = await self._user_repository.get_by_username(username)
        if not user:
            raise BusinessValidationError("User not found")
        return user

    async def authorize_redirect(
        self,
        request: Request,
        provider: ProviderLiteral,
        redirect_uri: str,
    ) -> httpx.Response:
        if provider not in self.__provider_property_map:
            raise BusinessValidationError(f"Unsupported provider: {provider}")
        oauth_provider = self.__provider_property_map[provider](self._oauth)
        return await oauth_provider.authorize_redirect(request, redirect_uri)  # type: ignore[attr-defined]

    async def authenticate_callback(
        self,
        request: Request,
        provider: ProviderLiteral,
    ) -> Tuple[User, OAuthAccount]:
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

        user_info_provider = self.__provider_userinfo_map[provider](self._oauth)  # type: ignore[arg-type]
        user_info: OAuthProviderUserInfo = await user_info_provider.fetch_user_info(token)

        oauth_account: Optional[OAuthAccount] = None
        if user_info.sub:
            oauth_account = await self._oauth_account_repository.get_by_provider_account(
                provider,
                user_info.sub,
            )

        user: Optional[User] = oauth_account.user if oauth_account else None
        if not user:
            user = await self._user_repository.get_by_username(user_info.username)

        created_user = False
        created_oauth_account = False

        if not user:
            user, oauth_account = await self.create_user(user_info, provider)
            created_user = True
            created_oauth_account = True
        elif not oauth_account:
            oauth_account = self.create_oauth_account(user, user_info, provider)
            created_oauth_account = True

        # if created_user:
        #     await self._user_repository.commit()
        # if created_oauth_account:
        #     await self._oauth_account_repository.commit()

        await self._organization_service.ensure_default_workspace_for_user(user)
        if not oauth_account and user_info.sub:
            oauth_account = await self._oauth_account_repository.get_by_provider_account(
                provider,
                user_info.sub,
            )
        if not oauth_account:
            raise BusinessValidationError("OAuth account not found for user")
        return user, oauth_account

    def create_oauth_account(
        self,
        user: User,
        user_info: OAuthProviderUserInfo,
        oauth_provider: ProviderLiteral,
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

    async def create_user(
        self,
        user_info: OAuthProviderUserInfo,
        oauth_provider: ProviderLiteral,
    ) -> Tuple[User, OAuthAccount]:
        if oauth_provider not in PROVIDERS:
            raise BusinessValidationError(f"Unsupported provider: {oauth_provider}")

        username = await self._resolve_unique_username(user_info)
        user_info.username = username

        user = User(
            id=uuid.uuid4(),
            username=username,
        )
        self._user_repository.add(user)
        oauth_account = self.create_oauth_account(user, user_info, oauth_provider)
        return user, oauth_account

    async def _resolve_unique_username(self, user_info: OAuthProviderUserInfo) -> str:
        base_username = user_info.username or ""

        if user_info.email and not base_username:
            base_username = user_info.email.split("@")[0]

        if not base_username:
            base_username = f"{user_info.provider}_{user_info.sub}"

        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "", base_username).lower()
        if not sanitized:
            sanitized = f"{user_info.provider}_{user_info.sub}"

        candidate = sanitized
        suffix = 1
        while await self._user_repository.get_by_username(candidate):
            candidate = f"{sanitized}{suffix}"
            suffix += 1

        return candidate
