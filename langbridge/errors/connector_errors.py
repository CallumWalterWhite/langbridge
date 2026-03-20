class ConnectorError(Exception):
    """Base exception for connector failures."""


class AuthError(ConnectorError):
    """Raised when connector authentication fails."""


class QueryValidationError(ConnectorError):
    """Raised when a query fails runtime validation."""


__all__ = [
    "AuthError",
    "ConnectorError",
    "QueryValidationError",
]
