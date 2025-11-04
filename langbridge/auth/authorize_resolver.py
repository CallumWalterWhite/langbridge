from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from db.base import AuthorizeBase
from db.connector import Connector
from db.auth import User

AuthorizeModelT = TypeVar("ModelT", bound=AuthorizeBase)

class AuthorizeResolver(ABC, Generic[AuthorizeModelT]):
    @abstractmethod
    def can_access(self, user: User, model: AuthorizeModelT) -> bool:
        """Determine if the user can access the given model."""
        raise NotImplementedError
 
class ConnectorAuthorizeResolver(AuthorizeResolver[Connector]):
    def can_access(self, user: User, model: Connector) -> bool:
        connector_org_ids = {org.id for org in model.organizations}
        connector_project_ids = {proj.id for proj in model.projects}
        return any(org.id in connector_org_ids for org in user.organizations) or any(
            proj.id in connector_project_ids for proj in user.projects
        )