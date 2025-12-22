class SemanticModelError(Exception):
    """Raised when the semantic model cannot satisfy a query."""


class SemanticQueryError(Exception):
    """Raised when the semantic query is invalid or unsupported."""


class JoinPathError(SemanticQueryError):
    """Raised when the required join path cannot be resolved."""
