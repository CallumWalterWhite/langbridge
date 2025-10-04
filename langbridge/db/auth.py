from sqlalchemy import Column, String, UUID, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey

from .base import Base

class Organization(Base):
    """Organization entity stored in the relational database."""

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    users: Mapped[list["User"]] = relationship(
        secondary="organization_user_association",
        back_populates="organizations",
    )
    
class Project(Base):
    """Project entity stored in the relational database."""

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    organization: Mapped[Organization] = relationship()
    users: Mapped[list["User"]] = relationship(
        secondary="project_user_association",
        back_populates="projects",
    )

organization_user_table = Table(
    "organization_user_association",
    Base.metadata,
    Column("organization_id", ForeignKey("organizations.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    """User entity stored in the relational database."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    organizations: Mapped[list[Organization]] = relationship(
        secondary=organization_user_table,
        back_populates="users",
    )
    projects: Mapped[list[Project]] = relationship(
        secondary="project_user_association",
        back_populates="users",
    )

class OAuthAccount(Base):
    """OAuth account linked to a user."""

    __tablename__ = "oauth_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user: Mapped[User] = relationship(back_populates="oauth_accounts")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    sub = Column(String(255), nullable=True)
    provider_account_id = Column(String(255), nullable=True)

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
