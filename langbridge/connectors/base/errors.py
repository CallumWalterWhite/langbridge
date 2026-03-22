class ConnectorError(Exception):
    """Base exception for connector errors."""
    pass

class ConnectionError(ConnectorError):
    """Raised when a connection to the data source fails."""

class AuthError(ConnectorError):
    """Raised when connector authentication fails."""

class QueryValidationError(ConnectorError):
    """Raised when a query fails runtime validation."""

class ConnectorTypeError(ConnectorError):
    """Raised when an unsupported connector type is encountered."""