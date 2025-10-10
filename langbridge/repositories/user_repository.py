import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.auth import OAuthAccount, User
from .base import BaseRepository


class UserRepository(BaseRepository):
    """Data access helper for user entities."""

    def __init__(self, session: Session):
        super().__init__(session, User)

    def get_by_username(self, username: str) -> User | None:
        return (
            self._session.query(User)
            .filter(User.username == username)
            .one_or_none()
        )
    
class OAuthAccountRepository(BaseRepository):
    """Data access helper for OAuth account entities."""

    def __init__(self, session: Session):
        super().__init__(session, OAuthAccount)

    def get_by_provider_account(self, provider: str, provider_account_id: str) -> OAuthAccount | None:
        return (
            self._session.query(OAuthAccount)
            .filter(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
            .one_or_none()
        )
