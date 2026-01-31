
from typing import Optional
import uuid
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

from langbridge.apps.api.langbridge_api.services.jobs.agent_job_request_service import AgentJobRequestService
from langbridge.packages.common.langbridge_common.contracts.jobs.agent_job import CreateAgentJobRequest
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.threads import Role, Thread, ThreadMessage, ThreadState, ToolCall
from langbridge.packages.common.langbridge_common.errors.application_errors import (
    BusinessValidationError,
    PermissionDeniedBusinessValidationError,
    ResourceNotFound,
)
from langbridge.packages.common.langbridge_common.contracts.auth import UserResponse
from langbridge.packages.common.langbridge_common.contracts.threads import ThreadCreateRequest, ThreadMessageResponse, ThreadResponse, ThreadUpdateRequest
from langbridge.packages.common.langbridge_common.repositories.organization_repository import ProjectRepository
from langbridge.packages.common.langbridge_common.repositories.thread_message_repository import ThreadMessageRepository
from langbridge.packages.common.langbridge_common.repositories.thread_repository import ThreadRepository
from langbridge.packages.common.langbridge_common.repositories.tool_call_repository import ToolCallRepository
from langbridge.apps.api.langbridge_api.services.organization_service import OrganizationService


class ThreadService:
    """Domain logic for managing conversation threads."""

    def __init__(
        self,
        thread_repository: ThreadRepository,
        thread_message_repository: ThreadMessageRepository,
        tool_call_repository: ToolCallRepository,
        project_repository: ProjectRepository,
        organization_service: OrganizationService,
        agent_job_request: AgentJobRequestService,
    ) -> None:
        self._thread_repository = thread_repository
        self._thread_message_repository = thread_message_repository
        self._tool_call_repository = tool_call_repository
        self._project_repository = project_repository
        self._organization_service = organization_service
        self._agent_job_request_service = agent_job_request

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
            status=ThreadState.awaiting_user_input,
        )

        self._thread_repository.add(thread)
        
        return ThreadResponse.model_validate(thread)

    async def get_thread_for_user(self, thread_id: uuid.UUID, user: UserResponse) -> Thread:
        thread = await self._thread_repository.get_for_user(thread_id, user.id)
        if thread is None:
            raise ResourceNotFound("Thread not found")
        return thread

    async def delete_thread(self, thread_id: uuid.UUID, user: UserResponse) -> None:
        thread = await self.get_thread_for_user(thread_id, user)
        await self._thread_repository.delete(thread)
        

    async def update_thread(
        self,
        thread_id: uuid.UUID,
        user: UserResponse,
        *,
        request: ThreadUpdateRequest,
    ) -> ThreadResponse:
        thread = await self.get_thread_for_user(thread_id, user)

        if request.title is not None:
            thread.title = request.title
        if request.metadata_json is not None:
            if not isinstance(request.metadata_json, dict):
                raise BusinessValidationError("metadata_json must be an object if provided.")
            thread.metadata_json = request.metadata_json

        thread.updated_at = datetime.now(timezone.utc)
        return ThreadResponse.model_validate(thread)

    async def list_messages_for_thread(
        self,
        thread_id: uuid.UUID,
        user: UserResponse,
    ) -> list[ThreadMessageResponse]:
        await self.get_thread_for_user(thread_id, user)
        messages = await self._thread_message_repository.list_for_thread(thread_id)
        return [ThreadMessageResponse.model_validate(message) for message in messages]

    async def create_user_thread_message(
        self,
        thread_id: uuid.UUID,
        user: UserResponse,
        organisation_id: uuid.UUID,
        agent_definition_id: uuid.UUID,
        content: dict,
        project_id: Optional[uuid.UUID] = None,
    ) -> ThreadMessageResponse:
        thread = await self.get_thread_for_user(thread_id, user)
        
        message = ThreadMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            role=Role.user,
            content=content,
        )

        await self._thread_message_repository.add(message)
        
        await self._agent_job_request_service.create_agent_job_request(
            request=CreateAgentJobRequest(
                job_type=JobType.AGENT,
                agent_definition_id=agent_definition_id,
                organisation_id=organisation_id,
                project_id=project_id,
                thread_message_id=message.id,
            )
        )
        
        return ThreadMessageResponse.model_validate(message)

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

        tool_calls = response.get("tool_calls")
        added_tool_calls = False
        if isinstance(tool_calls, list):
            for entry in tool_calls:
                if not isinstance(entry, dict):
                    continue
                tool_name = entry.get("tool_name") or entry.get("name") or entry.get("tool")
                if not tool_name:
                    continue
                duration_ms = entry.get("duration_ms")
                if isinstance(duration_ms, float):
                    duration_ms = int(duration_ms)
                elif not isinstance(duration_ms, int):
                    duration_ms = None
                self._tool_call_repository.add(
                    ToolCall(
                        id=uuid.uuid4(),
                        message_id=assistant_message_id,
                        tool_name=str(tool_name),
                        arguments=jsonable_encoder(entry.get("arguments") or {}),
                        result=jsonable_encoder(entry.get("result")),
                        duration_ms=duration_ms,
                        error=jsonable_encoder(entry.get("error"))
                        if entry.get("error") is not None
                        else None,
                    )
                )
                added_tool_calls = True
        if added_tool_calls:
            await self._tool_call_repository.flush()
