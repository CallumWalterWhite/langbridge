
import enum
import uuid
from ..base import BaseMessagePayload, register_payload

class AgentJobType(str, enum.Enum):
    """Enumeration of agent job types."""
    thread_request = "thread_request"

@register_payload("agent_job_request")
class AgentJobRequestMessage(BaseMessagePayload):
    """Payload for requesting an agent job."""

    job_id: uuid.UUID
    job_type: AgentJobType