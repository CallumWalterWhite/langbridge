
from langbridge.packages.common.langbridge_common.contracts.jobs.agent_job import CreateAgentJobRequest
from langbridge.packages.common.langbridge_common.repositories.job_repository import JobRepository


class AgentJobService:
    def __init__(self, 
                 job_repository: JobRepository):
        self._job_repository = job_repository
        
    async def create_agent_job(
        self,
        create_request: CreateAgentJobRequest,
    ):
        pass
        
    