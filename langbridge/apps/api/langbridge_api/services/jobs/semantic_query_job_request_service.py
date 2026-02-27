import logging
import uuid

from langbridge.apps.api.langbridge_api.services.task_dispatch_service import TaskDispatchService
from langbridge.packages.common.langbridge_common.contracts.connectors import ConnectorResponse
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
from langbridge.packages.common.langbridge_common.repositories.connector_repository import (
    ConnectorRepository,
)
from langbridge.packages.common.langbridge_common.repositories.semantic_model_repository import (
    SemanticModelRepository,
)
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.semantic_query import (
    SemanticQueryRequestMessage,
)


class SemanticQueryJobRequestService:
    def __init__(
        self,
        job_repository: JobRepository,
        task_dispatch_service: TaskDispatchService,
        semantic_model_repository: SemanticModelRepository,
        connector_repository: ConnectorRepository,
    ) -> None:
        self._job_repository = job_repository
        self._task_dispatch_service = task_dispatch_service
        self._semantic_model_repository = semantic_model_repository
        self._connector_repository = connector_repository
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

        semantic_model_yaml, connector_payload = await self._build_customer_runtime_context(request)

        message = SemanticQueryRequestMessage(
            job_id=job_id,
            job_type=JobType.SEMANTIC_QUERY,
            job_request=request.model_dump(mode="json"),
            semantic_model_yaml=semantic_model_yaml,
            connector=connector_payload,
        )
        await self._task_dispatch_service.dispatch_job_message(
            tenant_id=request.organisation_id,
            payload=message,
            required_tags=["semantic_query"],
        )
        return job_record

    async def _build_customer_runtime_context(
        self,
        request: CreateSemanticQueryJobRequest,
    ) -> tuple[str | None, dict | None]:
        if request.query_scope != "semantic_model" or request.semantic_model_id is None:
            return None, None

        semantic_model = await self._semantic_model_repository.get_for_scope(
            model_id=request.semantic_model_id,
            organization_id=request.organisation_id,
        )
        if semantic_model is None:
            return None, None

        connector = await self._connector_repository.get_by_id(semantic_model.connector_id)
        if connector is None:
            return semantic_model.content_yaml, None

        connector_response = ConnectorResponse.from_connector(
            connector,
            organization_id=request.organisation_id,
            project_id=request.project_id,
        )
        return semantic_model.content_yaml, connector_response.model_dump(mode="json")
