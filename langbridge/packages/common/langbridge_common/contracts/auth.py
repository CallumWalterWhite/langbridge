import uuid
from typing import Optional

from pydantic import ConfigDict, Field

from .base import _Base


class LoginRequest(_Base):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=255)


class RegisterRequest(LoginRequest):
    pass


class NativeLoginRequest(_Base):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class NativeRegisterRequest(NativeLoginRequest):
    username: Optional[str] = Field(default=None, min_length=3, max_length=255)


class LoginResponse(_Base):
    access_token: str
    token_type: str = "basic"


class UserResponse(_Base):
    id: uuid.UUID
    username: str
    email: Optional[str] = None
    is_active: bool
    
    available_organizations: Optional[list[uuid.UUID]] = None
    current_organization: Optional[uuid.UUID] = None
    available_projects: Optional[list[uuid.UUID]] = None
    current_project: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class OAuthAccountResponse(_Base):
    id: uuid.UUID
    provider: str
    provider_account_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    sub: Optional[str] = None

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
