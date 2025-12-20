import uuid
from models.auth import UserResponse
from db.auth import Organization, Project

class UserAuthorizedProvider:
    @staticmethod
    def organization_has_access(user: UserResponse, organization_id: uuid.UUID) -> bool:
        return any(org_id == organization_id for org_id in user.available_organizations)
    
    @staticmethod
    def user_in_at_least_one_organization(user: UserResponse, organization_ids: list[uuid.UUID] | list[Organization]) -> bool:
        if type(organization_ids[0]) is Organization:
            organization_ids = [org.id for org in organization_ids]  # type: ignore
        return any(org_id in organization_ids for org_id in user.available_organizations)
    
    @staticmethod
    def user_in_at_least_one_project(user: UserResponse, project_ids: list[uuid.UUID] | list[Project]) -> bool:
        if type(project_ids[0]) is Project:
            project_ids = [proj.id for proj in project_ids]  # type: ignore
        return any(proj_id in project_ids for proj_id in user.available_projects)
    
    @staticmethod
    def project_has_access(user: UserResponse, project_id: uuid.UUID) -> bool:
        return any(proj_id == project_id for proj_id in user.available_projects)