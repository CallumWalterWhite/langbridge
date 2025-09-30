from __future__ import annotations
import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=255)


class RegisterRequest(LoginRequest):
    pass


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "basic"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class AuthRegistry(BaseModel):
    type: str
    client_id: str
    client_secret: str
    authorize_url: str
    access_token_url: str
    api_base_url: str
    scopes: list[str] = Field(default_factory=list)

class AuthManifest(BaseModel):
    registries: list[AuthRegistry] = Field(default_factory=list)