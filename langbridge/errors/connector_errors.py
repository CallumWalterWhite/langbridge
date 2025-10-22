class ConnectorError(RuntimeError):
    """Base error for connector issues."""


class AuthError(ConnectorError):
    """Raised when authentication fails."""


class PermissionError(ConnectorError):
    """Raised when permissions are insufficient to run a query."""


class TimeoutError(ConnectorError):
    """Raised when a query times out."""


class QueryValidationError(ConnectorError):
    """Raised when an invalid or unsafe query is detected."""