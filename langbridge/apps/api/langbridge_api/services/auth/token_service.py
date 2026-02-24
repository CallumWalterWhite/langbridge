import secrets
import uuid
from langbridge.apps.api.langbridge_api.repositories.token_repository import UserPATRepository
from langbridge.packages.common.langbridge_common.contracts.auth import UserPATResponse
from langbridge.packages.common.langbridge_common.db.auth import UserPAT
from .auth_service import AuthService

class TokenService:
    def __init__(self, 
                 auth_service: AuthService,
                 user_pat_repository: UserPATRepository):
        self.auth_service = auth_service
        self.user_pat_repository = user_pat_repository

    def create_personal_access_token(self, user_id: uuid.UUID, name: str) -> UserPATResponse:
        token = self._generate_pat_token()
        user_pat = UserPAT(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            token=token
        )
        self.user_pat_repository.add(user_pat)
        return UserPATResponse(
            id=user_pat.id,
            name=user_pat.name,
            token=token
        )
    
    async def authenticate_with_pat(self, token: str) -> UserPATResponse | None:
        user_pat = await self.user_pat_repository.get_by_token(token)
        if not user_pat:
            return None
        
        user = await self.auth_service.get_user_by_id(user_pat.user_id)
        if not user:
            return None
        
        return UserPATResponse(
            id=user_pat.id,
            name=user_pat.name,
            token=None  # Do not return the token on retrieval
        )

    def _generate_pat_token(self) -> str:
        return secrets.token_urlsafe(32)