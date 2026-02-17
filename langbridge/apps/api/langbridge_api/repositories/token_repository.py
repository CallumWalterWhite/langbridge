import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from langbridge.packages.common.langbridge_common.db.auth import UserPAT

from .base import AsyncBaseRepository


class UserPATRepository(AsyncBaseRepository[UserPAT]):
    """Data access helper for user personal access tokens."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserPAT)

    async def get_by_token(self, token: str) -> UserPAT | None:
        stmt = select(UserPAT).filter(UserPAT.token_hash == token)
        result = await self._session.scalars(stmt)
        return result.first()