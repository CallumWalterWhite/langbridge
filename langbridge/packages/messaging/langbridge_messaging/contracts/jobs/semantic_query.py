import uuid

from langbridge.packages.common.langbridge_common.contracts.jobs.type import JobType

from ..base import BaseMessagePayload, register_payload


@register_payload("semantic_query_request")
class SemanticQueryRequestMessage(BaseMessagePayload):
    """Payload for requesting worker-based semantic query execution."""

    job_id: uuid.UUID
    job_type: JobType
