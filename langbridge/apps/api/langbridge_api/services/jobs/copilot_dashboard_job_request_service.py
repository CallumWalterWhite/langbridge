from __future__ import annotations

import logging
import uuid

from langbridge.apps.api.langbridge_api.services.message.message_serivce import MessageService
from langbridge.packages.common.langbridge_common.contracts.jobs.copilot_dashboard_job import (
    CreateCopilotDashboardJobRequest,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.job import (
    JobEventRecord,
    JobEventVisibility,
    JobRecord,
    JobStatus,
)
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.repositories.agent_repository import AgentRepository
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import (
    SemanticModelRepository,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.copilot_dashboard import (
    CopilotDashboardRequestMessage,
)


class CopilotDashboardJobRequestService:
    def __init__(
        self,
        job_repository: JobRepository,
        agent_definition_repository: AgentRepository,
        semantic_model_repository: SemanticModelRepository,
        message_service: MessageService,
    ) -> None:
        self._job_repository = job_repository
        self._agent_definition_repository = agent_definition_repository
        self._semantic_model_repository = semantic_model_repository
        self._message_service = message_service
        self._logger = logging.getLogger(__name__)

    async def create_copilot_dashboard_job_request(
        self,
        request: CreateCopilotDashboardJobRequest,
    ) -> JobRecord:
        agent = await self._agent_definition_repository.get_by_id(request.agent_definition_id)
        if agent is None:
            raise BusinessValidationError("Agent definition not found.")

        semantic_model = await self._semantic_model_repository.get_for_scope(
            model_id=request.semantic_model_id,
            organization_id=request.organisation_id,
        )
        if semantic_model is None:
            raise BusinessValidationError("Semantic model not found.")

        job_id = uuid.uuid4()
        job_record = JobRecord(
            id=job_id,
            job_type=JobType.COPILOT_DASHBOARD.value,
            payload=request.model_dump(mode="json"),
            headers={},
            organisation_id=str(request.organisation_id),
            status=JobStatus.queued,
            progress=0,
            status_message="Copilot dashboard request queued.",
            job_events=[
                JobEventRecord(
                    event_type="CopilotDashboardQueued",
                    visibility=JobEventVisibility.public,
                    details={
                        "visibility": "public",
                        "message": "Copilot dashboard request queued.",
                        "source": "api",
                        "details": {
                            "agent_definition_id": str(request.agent_definition_id),
                            "semantic_model_id": str(request.semantic_model_id),
                        },
                    },
                )
            ],
        )
        self._job_repository.add(job_record)

        message = CopilotDashboardRequestMessage(
            job_id=job_id,
            job_type=JobType.COPILOT_DASHBOARD,
        )
        await self._message_service.create_outbox_message(payload=message)

        self._logger.info(
            "Created BI copilot dashboard job %s for agent %s",
            job_id,
            request.agent_definition_id,
        )
        return job_record
