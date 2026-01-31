import logging
from langbridge.packages.messaging.langbridge_messaging.contracts.base import MessageType
from langbridge.packages.messaging.langbridge_messaging.contracts.jobs.agent_job import AgentJobRequestMessage
from langbridge.packages.messaging.langbridge_messaging.handler import BaseMessageHandler

class JobHandlerMessage(BaseMessageHandler):
    message_type: MessageType = MessageType.AGENT_JOB_REQUEST
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
    
    async def handle(self, agent_job_request_payload: AgentJobRequestMessage) -> None:
        self._logger.info(f"Received Agent Job Request: {agent_job_request_payload.job_id}")
        self._logger.info(f"Received Agent Job Request: {agent_job_request_payload.job_type}")
        # Implement the logic to handle the agent job request here
        return None