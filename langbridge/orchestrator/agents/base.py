from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class AgentSpecification(BaseModel):
    name: str
    description: str
    version: str
    capabilities: list[str]
    task_types: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    constraints: list[str]
    refusal_conditions: list[str] = []
    side_effects: bool = False
    cost_profile: str = "low"  # low | medium | high
    latency_profile: str = "low"
    risk_profile: str = "low"
    required_context: list[str] = []
    verification_contract: dict[str, Any] = {}
    routing_examples: list[dict[str, str]] = []


class AgentTask(BaseModel):
    task_type: str
    question: str | None = None
    input: dict[str, Any] = {}
    context: dict[str, Any] = {}
    expected_output: dict[str, Any] = {}

class AgentResult(BaseModel):
    status: str
    output: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}
    error: str | None = None
    confidence: float | None = None

class BaseAgent(ABC): 
    @classmethod
    @abstractmethod
    def specification(cls) -> AgentSpecification:
        ...

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        ...