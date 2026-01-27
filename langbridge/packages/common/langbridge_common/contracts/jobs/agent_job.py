from ..base import _Base

class CreateAgentJobRequest(_Base):
    job_type: str
    payload: dict