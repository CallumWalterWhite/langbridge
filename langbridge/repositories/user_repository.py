from __future__ import annotations
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import User
from .base import BaseRepository


class UserRepository(BaseRepository):
    """Data access helper for user entities."""

    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_username(self, username: str) -> User | None:
        return (
            self._session.query(User)
            .filter(User.username == username)
            .one_or_none()
        )
    
    def get_all(self) -> list[User]:
        return self._session.query(User).all()

    def create_user(self, username: str, hashed_password: str, is_active: bool = True) -> User:
        user = User(id=uuid.uuid4(), username=username, hashed_password=hashed_password, is_active=is_active)
        self._session.add(user)
        return user

    def create_if_not_exists(self, username: str, hashed_password: str, is_active: bool = True) -> User:
        existing = self.get_by_username(username)
        if existing:
            return existing
        try:
            return self.create_user(username=username, hashed_password=hashed_password, is_active=is_active)
        except IntegrityError:
            raise ValueError(f"User with username '{username}' already exists")
