class ExecutionRuntimeError(Exception):
    """Base exception for execution runtime errors."""
    pass

class ExecutionValidationError(ExecutionRuntimeError):
    """Raised when execution fails runtime validation."""
    
    