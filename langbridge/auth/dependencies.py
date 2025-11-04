

from fastapi import HTTPException, Request, status
from dependency_injector.wiring import inject

from models.auth import UserResponse


@inject
def get_current_user(
    request: Request
) -> UserResponse:
    if request.state.user:
        return request.state.user
    
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")
