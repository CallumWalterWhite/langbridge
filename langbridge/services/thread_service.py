
import uuid

from db.threads import Thread, ThreadStatus
from errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from models.auth import UserResponse
from models.threads import ThreadCreateRequest, ThreadResponse
from repositories.organization_repository import ProjectRepository
from repositories.thread_repository import ThreadRepository
from services.organization_service import OrganizationService


class ThreadService:
    """Domain logic for managing conversation threads."""

    def __init__(
        self,
        thread_repository: ThreadRepository,
        project_repository: ProjectRepository,
        organization_service: OrganizationService,
    ) -> None:
        self._thread_repository = thread_repository
        self._project_repository = project_repository
        self._organization_service = organization_service

    async def list_threads_for_user(self, user: UserResponse) -> list[ThreadResponse]:
        threads = await self._thread_repository.list_for_user(user.id)
        return [ThreadResponse.model_validate(thread) for thread in threads]

    async def _resolve_project_id(self, request: ThreadCreateRequest, user: UserResponse) -> uuid.UUID:
        if request.project_id:
            project = await self._project_repository.get_by_id(request.project_id)
            if project is None:
                raise ResourceNotFound("Project not found")

            user_projects = await self._project_repository.list_for_user(user.id)
            if not any(p.id == project.id for p in user_projects):
                raise PermissionDeniedBusinessValidationError(
                    "You do not have access to the requested project."
                )
            return project.id

        _, project = await self._organization_service.ensure_default_workspace_for_user(user)
        return project.id

    async def create_thread(
        self,
        request: ThreadCreateRequest,
        user: UserResponse,
    ) -> ThreadResponse:
        project_id = await self._resolve_project_id(request, user)

        metadata = request.metadata_json or {}
        if not isinstance(metadata, dict):
            raise BusinessValidationError("metadata_json must be an object if provided.")

        thread = Thread(
            id=uuid.uuid4(),
            project_id=project_id,
            title=request.title,
            created_by=user.id,
            status=ThreadStatus.active,
        )

        self._thread_repository.add(thread)
        await self._thread_repository.flush()
        return ThreadResponse.model_validate(thread)

    async def get_thread_for_user(self, thread_id: uuid.UUID, user: UserResponse) -> Thread:
        thread = await self._thread_repository.get_for_user(thread_id, user.id)
        if thread is None:
            raise ResourceNotFound("Thread not found")
        return thread

    async def delete_thread(self, thread_id: uuid.UUID, user: UserResponse) -> None:
        thread = await self.get_thread_for_user(thread_id, user)
        await self._thread_repository.delete(thread)
