from __future__ import annotations

import uuid
from typing import List

from pydantic import ConfigDict, Field

from db.auth import InviteStatus
from utils.schema import _to_camel
from .base import _Base


class ProjectResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=3, max_length=255)
    organization_id: uuid.UUID = Field(default_factory=uuid.uuid4)



class OrganizationResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=3, max_length=255)
    member_count: int = Field(default=0)
    projects: List[ProjectResponse] = Field(default_factory=list)


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

class ProjectInviteResponse(_Base):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: InviteStatus = Field(default=InviteStatus.PENDING)
    invitee_id: uuid.UUID   
    

    
