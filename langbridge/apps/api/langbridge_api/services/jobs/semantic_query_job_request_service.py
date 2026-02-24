import logging
import uuid

from langbridge.apps.api.langbridge_api.services.message.message_serivce import MessageService
from langbridge.packages.common.langbridge_common.contracts.jobs.semantic_query_job import (
    CreateSemanticQueryJobRequest,
)
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.job import (
    JobEventRecord,
    JobEventVisibility,
    JobRecord,
    JobStatus,
)
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.semantic_query import (
    SemanticQueryRequestMessage,
)


class SemanticQueryJobRequestService:
    def __init__(
        self,
        job_repository: JobRepository,
        message_service: MessageService,
    ) -> None:
        self._job_repository = job_repository
        self._message_service = message_service
        self._logger = logging.getLogger(__name__)

    async def create_semantic_query_job_request(
        self,
        request: CreateSemanticQueryJobRequest,
    ) -> JobRecord:
        job_id = uuid.uuid4()
        job_record = JobRecord(
            id=job_id,
            job_type=JobType.SEMANTIC_QUERY.value,
            payload=request.model_dump(mode="json"),
            headers={},
            organisation_id=str(request.organisation_id),
            status=JobStatus.queued,
            progress=0,
            status_message="Semantic query queued.",
            job_events=[
                JobEventRecord(
                    event_type="SemanticQueryQueued",
                    visibility=JobEventVisibility.public,
                    details={
                        "visibility": "public",
                        "message": "Semantic query queued.",
                        "source": "api",
                        "details": {
                            "query_scope": request.query_scope,
                            "semantic_model_id": (
                                str(request.semantic_model_id)
                                if request.semantic_model_id
                                else None
                            ),
                            "semantic_model_ids": [
                                str(model_id)
                                for model_id in (request.semantic_model_ids or [])
                            ],
                            "connector_id": (
                                str(request.connector_id)
                                if request.connector_id
                                else None
                            ),
                        },
                    },
                )
            ],
        )
        self._job_repository.add(job_record)
        self._logger.info(
            "Created semantic query job %s for scope %s",
            job_id,
            request.query_scope,
        )

        message = SemanticQueryRequestMessage(
            job_id=job_id,
            job_type=JobType.SEMANTIC_QUERY,
        )
        await self._message_service.create_outbox_message(payload=message)
        return job_record
