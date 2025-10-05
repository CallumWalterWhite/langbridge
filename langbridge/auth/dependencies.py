from __future__ import annotations

from fastapi import HTTPException, Request, status
from dependency_injector.wiring import inject

from db.auth import User


@inject
def get_current_user(
    request: Request
) -> User:
    if request.state.user:
        return request.state.user
    
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")
