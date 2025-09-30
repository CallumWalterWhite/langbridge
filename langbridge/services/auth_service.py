from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Optional

from db.models import User
from repositories.user_repository import UserRepository


class AuthService:
    """Domain logic for authenticating and registering users."""

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    def get_all_users(self) -> list[User]:
        return self._user_repository.get_all()

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self._user_repository.get_by_username(username)
        if not user:
            return None
        if not self._verify_password(password, user.hashed_password): # type: ignore
            return None
        return user

    def register(self, username: str, password: str) -> User:
        if self._user_repository.get_by_username(username):
            raise ValueError("User already exists")
        hashed_password = self._hash_password(password)
        return self._user_repository.create_user(username=username, hashed_password=hashed_password)

    def create_basic_token(self, username: str, password: str) -> str:
        raw = f"{username}:{password}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    def hash_password(self, password: str) -> str:
        return self._hash_password(password)

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _verify_password(self, password: str, hashed: str) -> bool:
        return hmac.compare_digest(self._hash_password(password), hashed)
