from typing import Dict, Optional


class ResourceNotFound(Exception):
    pass

class ResourceAlreadyExists(Exception):
    pass

class InvalidRequest(Exception):
    pass

class ApplicationError(Exception):
    pass

class InvalidResourceType(Exception):
    pass

class JWTError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class BusinessValidationError(Exception):
    def __init__(self, message: str, errors: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
        
    def __str__(self):
        return f"{self.message} - {self.errors}"

class InvalidInputBusinessValidationError(BusinessValidationError):
    def __init__(self, message: str, errors: Optional[Dict] = None):
        super().__init__(message, errors)

class QuotaExceededBusinessValidationError(BusinessValidationError):
    def __init__(self, message: str, errors: Optional[Dict] = None):
        super().__init__(message, errors)

class PermissionDeniedBusinessValidationError(BusinessValidationError):
    def __init__(self, message: str, errors: Optional[Dict] = None):
        super().__init__(message, errors)

class ExternalServiceError(Exception):
    pass