import uuid
from sqlalchemy import Boolean, Column, Integer, String, UUID

from .base import Base


class User(Base):
    """User entity stored in the relational database."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)