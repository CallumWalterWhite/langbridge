"""Exception hierarchy for langbridge connectors.

Every error raised by the connector framework or a connector implementation
derives from :class:`ConnectorError`, so callers can catch the whole family
with a single ``except`` clause.
"""

from __future__ import annotations


class ConnectorError(Exception):
    """Base class for every connector error."""


class ConnectorConfigError(ConnectorError):
    """Raised when connector configuration is invalid or incomplete."""


class ConnectorConnectionError(ConnectorError):
    """Raised when a connection to the data source cannot be established."""


class ConnectorAuthError(ConnectorError):
    """Raised when authentication with the data source fails."""


class ResourceNotFoundError(ConnectorError):
    """Raised when a requested resource is absent from the connector catalog."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"Resource '{resource}' was not found in the connector catalog")
        self.resource = resource


class QueryValidationError(ConnectorError):
    """Raised when a query fails read-only validation before execution."""


class QueryExecutionError(ConnectorError):
    """Raised when query execution against the data source fails."""


class MissingDependencyError(ConnectorError):
    """Raised when an optional driver dependency is not installed."""

    def __init__(self, connector: str, package: str, extra: str) -> None:
        super().__init__(
            f"The '{connector}' connector requires the '{package}' package. "
            f'Install it with: pip install "langbridge-connectors[{extra}]"'
        )
        self.connector = connector
        self.package = package
        self.extra = extra


class ConnectorNotRegisteredError(ConnectorError):
    """Raised when a connector key is not present in the registry."""

    def __init__(self, key: str, available: list[str]) -> None:
        listing = ", ".join(available) if available else "(none)"
        super().__init__(
            f"No connector registered under key '{key}'. Available connectors: {listing}"
        )
        self.key = key
