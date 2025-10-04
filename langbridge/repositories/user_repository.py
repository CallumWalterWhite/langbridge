from __future__ import annotations
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