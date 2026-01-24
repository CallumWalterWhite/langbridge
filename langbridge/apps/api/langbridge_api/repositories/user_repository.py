from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from langbridge.apps.api.langbridge_api.db.auth import OAuthAccount, User
from .base import AsyncBaseRepository


class UserRepository(AsyncBaseRepository[User]):
    """Data access helper for user entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.oauth_accounts))
            .filter(User.username == username)
        )
        return (await self._session.scalars(stmt)).one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.oauth_accounts))
            .filter(User.email == email)
        )
        return (await self._session.scalars(stmt)).one_or_none()
    
class OAuthAccountRepository(AsyncBaseRepository[OAuthAccount]):
    """Data access helper for OAuth account entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OAuthAccount)

    async def get_by_provider_account(self, provider: str, provider_account_id: str) -> OAuthAccount | None:
        stmt = (
            select(OAuthAccount)
            .options(selectinload(OAuthAccount.user))
            .filter(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        return (await self._session.scalars(stmt)).one_or_none()
