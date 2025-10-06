import enum
from typing import TYPE_CHECKING
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base
from db.associations import organization_connectors, project_connectors

if TYPE_CHECKING:
    from .connector import Connector

class InviteStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class OrganizationRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    OWNER = "owner"

class ProjectRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    OWNER = "owner"

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str]     = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user_links: Mapped[list["OrganizationUser"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        secondary="organization_user_association",
        back_populates="organizations",
        viewonly=True,
    )
    
    connectors: Mapped[list["Connector"]] = relationship(
        "Connector", secondary=organization_connectors, back_populates="organizations", viewonly=False
    )

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    invites:  Mapped[list["OrganizationInvite"]] = relationship("OrganizationInvite", back_populates="organization", cascade="all, delete-orphan")



class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")

    user_links: Mapped[list["ProjectUser"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    users: Mapped[list["User"]] = relationship(
        secondary="project_user_association",
        back_populates="projects",
        viewonly=True
    )
    
    connectors: Mapped[list["Connector"]] = relationship(
        "Connector", secondary=project_connectors, back_populates="projects", viewonly=False
    )

    invites: Mapped[list["ProjectInvite"]] = relationship("ProjectInvite", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_project_org_name"),)


class OrganizationUser(Base):
    __tablename__ = "organization_user_association"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    user_id: Mapped[uuid.UUID]         = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[OrganizationRole]     = mapped_column(SqlEnum(OrganizationRole, name="organization_role"), nullable=False, default=OrganizationRole.MEMBER)

    organization: Mapped["Organization"] = relationship(back_populates="user_links")
    user: Mapped["User"]                 = relationship(back_populates="organization_links")


class ProjectUser(Base):
    __tablename__ = "project_user_association"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[uuid.UUID]   = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[ProjectRole]     = mapped_column(SqlEnum(ProjectRole, name="project_role"), nullable=False, default=ProjectRole.MEMBER)

    project: Mapped["Project"] = relationship(back_populates="user_links")
    user: Mapped["User"] = relationship(back_populates="projects_links")



class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    organization_links: Mapped[list["OrganizationUser"]] = relationship(back_populates="user")
    organizations: Mapped[list["Organization"]] = relationship(
        secondary="organization_user_association",
        back_populates="users",
        viewonly=True,   # prevents double insertions
    )
    
    projects_links: Mapped[list["ProjectUser"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(
        secondary="project_user_association",
        back_populates="users",
        viewonly=True,
    )

    project_invites_received: Mapped[list["ProjectInvite"]] = relationship(
        "ProjectInvite",
        back_populates="invitee",
        foreign_keys="ProjectInvite.invitee_id",
        primaryjoin="User.id == ProjectInvite.invitee_id",
        cascade="all, delete-orphan",
    )

    project_invites_sent: Mapped[list["ProjectInvite"]] = relationship(
        "ProjectInvite",
        back_populates="inviter",
        foreign_keys="ProjectInvite.inviter_id",
        primaryjoin="User.id == ProjectInvite.inviter_id",
        cascade="all, delete-orphan",
    )



class OAuthAccount(Base):
    """OAuth account linked to a user."""

    __tablename__ = "oauth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user: Mapped[User] = relationship(back_populates="oauth_accounts")
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class OrganizationInvite(Base):
    """Invite for a user to join an organization."""

    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    inviter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    invitee_username: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InviteStatus] = mapped_column(SqlEnum(InviteStatus, name="invite_status"), nullable=False, default=InviteStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="invites",
    )
    inviter: Mapped[User] = relationship(
        "User",
        foreign_keys=[inviter_id],
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "invitee_username", name="uq_org_invite_username"),
    )


class ProjectInvite(Base):
    __tablename__ = "project_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    inviter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    invitee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[InviteStatus] = mapped_column(
        SqlEnum(InviteStatus, name="project_invite_status"),
        nullable=False, default=InviteStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="invites")

    inviter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[inviter_id],
        back_populates="project_invites_sent",
    )
    invitee: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invitee_id],
        back_populates="project_invites_received",
    )

    __table_args__ = (UniqueConstraint("project_id", "invitee_id", name="uq_project_invite_user"),)

