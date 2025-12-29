
import uuid
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from db.threads import Role, Thread, ThreadMessage, ThreadStatus
from errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from models.auth import UserResponse
from models.threads import ThreadCreateRequest, ThreadMessageResponse, ThreadResponse
from repositories.organization_repository import ProjectRepository
from repositories.thread_message_repository import ThreadMessageRepository
from repositories.thread_repository import ThreadRepository
from services.organization_service import OrganizationService


class ThreadService:
    """Domain logic for managing conversation threads."""

    def __init__(
        self,
        thread_repository: ThreadRepository,
        thread_message_repository: ThreadMessageRepository,
        project_repository: ProjectRepository,
        organization_service: OrganizationService,
    ) -> None:
        self._thread_repository = thread_repository
        self._thread_message_repository = thread_message_repository
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

    async def list_messages_for_thread(
        self,
        thread_id: uuid.UUID,
        user: UserResponse,
    ) -> list[ThreadMessageResponse]:
        await self.get_thread_for_user(thread_id, user)
        messages = await self._thread_message_repository.list_for_thread(thread_id)
        return [ThreadMessageResponse.model_validate(message) for message in messages]

    async def record_chat_turn(
        self,
        thread_id: uuid.UUID,
        user: UserResponse,
        *,
        prompt: str,
        response: dict,
        agent_snapshot: dict | None = None,
    ) -> None:
        thread = await self.get_thread_for_user(thread_id, user)
        agent_snapshot = agent_snapshot or {}

        user_message_id = uuid.uuid4()
        assistant_message_id = uuid.uuid4()

        thread.updated_at = datetime.now(timezone.utc)

        user_message = ThreadMessage(
            id=user_message_id,
            thread_id=thread.id,
            role=Role.user,
            content={"text": prompt},
            model_snapshot=agent_snapshot,
        )
        assistant_message = ThreadMessage(
            id=assistant_message_id,
            thread_id=thread.id,
            parent_message_id=user_message_id,
            role=Role.assistant,
            content={
                "summary": response.get("summary"),
                "result": jsonable_encoder(response.get("result")),
                "visualization": jsonable_encoder(response.get("visualization")),
                "diagnostics": response.get("diagnostics"),
            },
            model_snapshot=agent_snapshot,
            error=response.get("error"),
        )

        self._thread_message_repository.add(user_message)
        self._thread_message_repository.add(assistant_message)
        await self._thread_message_repository.flush()
