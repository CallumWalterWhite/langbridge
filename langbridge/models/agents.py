from datetime import datetime, timezone
from typing import List, Literal
from pydantic import BaseModel, ConfigDict, Field
from utils.schema import _to_camel
from .base import _Base


AgentKind = Literal['sql_analyst', 'docs_qa', 'hybrid']

class Agent(_Base):
    id: str
    name: str
    kind: AgentKind
    source_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, frozen=True)


class AgentCreate(_Base):
    name: str
    kind: AgentKind
    source_ids: List[str] = Field(default_factory=list)


class AgentCreateResponse(_Base):
    id: str