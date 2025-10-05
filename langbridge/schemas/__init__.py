
from schemas.organizations import (
    InviteUserRequest, 
    OrganizationCreateRequest, 
    OrganizationInviteResponse, 
    OrganizationResponse, 
    ProjectCreateRequest, 
    ProjectInviteResponse, 
    ProjectResponse
)

def _rebuild_model(m):
    try:
        rebuild = getattr(m, "model_rebuild", None)
        if callable(rebuild):
            rebuild(recursive=True)
            return
    except Exception:
        pass
    # Fallback for Pydantic v1
    try:
        upd = getattr(m, "update_forward_refs", None)
        if callable(upd):
            upd()
    except Exception:
        pass

for m in [
    OrganizationCreateRequest,
    ProjectCreateRequest,
    InviteUserRequest,
    OrganizationResponse,
    ProjectResponse,
    OrganizationInviteResponse,
    ProjectInviteResponse,
]:
    _rebuild_model(m)

__all__ = [
    "InviteUserRequest",
    "OrganizationCreateRequest",
    "OrganizationInviteResponse",
    "OrganizationResponse",
    "ProjectCreateRequest",
    "ProjectInviteResponse",
    "ProjectResponse",
]
