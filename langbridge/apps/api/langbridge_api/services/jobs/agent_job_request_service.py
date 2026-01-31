
import logging
import uuid
from langbridge.apps.api.langbridge_api.services.message.message_serivce import MessageService
from langbridge.packages.common.langbridge_common.contracts.jobs.agent_job import CreateAgentJobRequest
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.errors.application_errors import BusinessValidationError
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository
from langbridge.packages.common.langbridge_common.repositories.agent_repository import AgentRepository
from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType
from langbridge.packages.common.langbridge_common.db.job import JobRecord, JobEventRecord
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.agent_job import AgentJobRequestMessage


class AgentJobRequestService:
    def __init__(self, 
                    job_repository: JobRepository,
                    agent_repository: AgentRepository,
                    message_service: MessageService):
        self._job_repository = job_repository
        self._agent_repository = agent_repository
        self._message_service = message_service
        self._logger = logging.getLogger(__name__)
        
    async def create_agent_job(
        self,
        request: CreateAgentJobRequest,
    ) -> JobRecord:
        agent = await self._agent_repository.get_by_id(request.agent_definition_id)
        if agent is None:
            raise BusinessValidationError(f"Agent definition with ID {request.agent_definition_id} does not exist.")
        
        job_id = uuid.uuid4()
        
        job_record = JobRecord(
            id=job_id,
            job_type=JobType.AGENT,
            payload=request.dict_json(),
            organisation_id=request.organisation_id,
            job_events=[
                JobEventRecord(
                    event_type="AgentJobCreated",
                    details={"agent_definition_id": str(request.agent_definition_id)}
                )
            ],
        )
        
        job = await self._job_repository.add(job_record)
        
        self._logger.info(f"Created agent job with ID {job.id} for agent definition ID {request.agent_definition_id}")
        
        agent_job_message = AgentJobRequestMessage(
            job_id=job_id,
            job_type=JobType.AGENT,
        )
        
        await self._message_service.create_outbox_message(
            message=agent_job_message
        )
        
        return job
        