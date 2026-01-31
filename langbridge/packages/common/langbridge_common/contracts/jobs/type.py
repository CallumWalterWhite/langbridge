from enum import Enum


class JobType(str, Enum):
    AGENT = "agent"
    SEMANTIC_QUERY = "semantic_query"