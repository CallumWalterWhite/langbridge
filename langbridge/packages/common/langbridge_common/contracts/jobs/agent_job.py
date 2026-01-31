import uuid
from .type import JobType
from ..base import _Base

class CreateAgentJobRequest(_Base):
    job_type: JobType
    agent_definition_id: uuid.UUID
    organisation_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    thread_id: uuid.UUID