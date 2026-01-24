from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass

class AuthorizeBase:
    """Base class for authorization resolvers."""
    pass