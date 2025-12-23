

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

@inject
def has_organization_access(
    request: Request
) -> UserResponse:
    user: UserResponse = get_current_user(request)
    if request.path_params.get("organization_id") is None:
        return user
    if request.path_params.get("organization_id") not in [str(org) for org in user.available_organizations]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user

@inject
def has_project_access(
    request: Request
) -> UserResponse:
    user: UserResponse = get_current_user(request)
    if request.path_params.get("project_id") is None:
        return user
    if request.path_params.get("project_id") not in [str(proj) for proj in user.available_projects]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user