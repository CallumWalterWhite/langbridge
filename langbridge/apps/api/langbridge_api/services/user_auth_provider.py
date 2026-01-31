import uuid
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.db.auth import Organization, Project
from langbridge.apps.api.langbridge_api.services.service_utils import is_internal_service_call

class UserAuthorizedProvider:
    @staticmethod
    def organization_has_access(user: UserResponse, organization_id: uuid.UUID) -> bool:
        if is_internal_service_call():
            return True
        return any(org_id == organization_id for org_id in user.available_organizations)
    
    @staticmethod
    def user_in_at_least_one_organization(user: UserResponse, organization_ids: list[uuid.UUID] | list[Organization]) -> bool:
        if is_internal_service_call():
            return True
        print("organization_ids:", organization_ids)
        print(user.available_organizations)
        if type(organization_ids) is list and len(organization_ids) > 0 and type(organization_ids[0]) is Organization:
            organization_ids = [org.id for org in organization_ids]  # type: ignore
        return any(org_id in organization_ids for org_id in user.available_organizations) # type: ignore
    
    @staticmethod
    def user_in_at_least_one_project(user: UserResponse, project_ids: list[uuid.UUID] | list[Project]) -> bool:
        if is_internal_service_call():
            return True
        if type(project_ids) is list and len(project_ids) > 0 and type(project_ids[0]) is Project:
            project_ids = [proj.id for proj in project_ids]  # type: ignore
        return any(proj_id in project_ids for proj_id in user.available_projects) # type: ignore
    
    @staticmethod
    def project_has_access(user: UserResponse, project_id: uuid.UUID) -> bool:
        if is_internal_service_call():
            return True
        return any(proj_id == project_id for proj_id in user.available_projects) # type: ignore
