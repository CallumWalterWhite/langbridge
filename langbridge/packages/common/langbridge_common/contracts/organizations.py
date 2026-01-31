import uuid
from typing import List

from pydantic import ConfigDict, Field

from langbridge.packages.common.langbridge_common.db.auth import InviteStatus
from .base import _Base


class ProjectResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=3, max_length=255)
    organization_id: uuid.UUID = Field(default_factory=uuid.uuid4)

    model_config = ConfigDict(from_attributes=True)


class OrganizationResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=3, max_length=255)
    member_count: int = Field(default=0)
    projects: List[ProjectResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class OrganizationCreateRequest(_Base):
    name: str


class ProjectCreateRequest(_Base):
    name: str = Field(min_length=3, max_length=255)


class InviteUserRequest(_Base):
    username: str = Field(min_length=3, max_length=255)


class OrganizationInviteResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: InviteStatus = Field(default=InviteStatus.PENDING)
    invitee_username: str = Field(min_length=3, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class ProjectInviteResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: InviteStatus = Field(default=InviteStatus.PENDING)
    invitee_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

class OrganizationEnvironmentSetting(_Base):
    setting_key: str = Field(min_length=1, max_length=255)
    setting_value: str  # Encrypted value

    model_config = ConfigDict(from_attributes=True)
