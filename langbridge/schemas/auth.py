from __future__ import annotations
from .base import _Base
import uuid

from pydantic import ConfigDict, Field


class LoginRequest(_Base):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=255)


class RegisterRequest(LoginRequest):
    pass


class LoginResponse(_Base):
    access_token: str
    token_type: str = "basic"


class UserResponse(_Base):
    id: uuid.UUID
    username: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class AuthRegistry(_Base):
    type: str
    client_id: str
    client_secret: str
    authorize_url: str
    access_token_url: str
    api_base_url: str
    scopes: list[str] = Field(default_factory=list)

class AuthManifest(_Base):
    registries: list[AuthRegistry] = Field(default_factory=list)

class CurrentUser(_Base):
    username: str