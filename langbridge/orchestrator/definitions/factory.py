from typing import Set
import uuid

from .model import (
    AgentDefinitionModel,
    MemoryStrategy,
    ExecutionMode,
    OutputFormat,
)


class AgentDefinitionFactory:
    """Factory for creating and validating AgentDefinitionModel instances."""

    def create_agent_definition(self, definition: dict) -> AgentDefinitionModel:
        """
        Creates an AgentDefinitionModel from a dictionary and validates
        combinations that Pydantic alone might miss.
        """
        model = AgentDefinitionModel.model_validate(definition)
        self._validate_combinations(model)
        return model
    
    def validate_agent_definition(self, definition: dict) -> None:
        model = AgentDefinitionModel.model_validate(definition)
        self._validate_combinations(model)

    def _validate_combinations(self, model: AgentDefinitionModel) -> None:
        """Performs cross-field validation on the agent definition."""
        self._validate_memory(model)
        self._validate_access_policy(model)
        self._validate_execution(model)
        self._validate_output(model)

    def _validate_memory(self, model: AgentDefinitionModel) -> None:
        strategy = model.memory.strategy
        
        if strategy == MemoryStrategy.vector and not model.memory.vector_index:
            raise ValueError(
                "Memory strategy 'vector' requires 'vector_index' to be set."
            )
            
        if strategy == MemoryStrategy.database and not model.memory.database_table:
            raise ValueError(
                "Memory strategy 'database' requires 'database_table' to be set."
            )
            
        if strategy == MemoryStrategy.transient and model.memory.ttl_seconds is None:
            raise ValueError(
                "Memory strategy 'transient' requires 'ttl_seconds' to be set."
            )

    def _validate_access_policy(self, model: AgentDefinitionModel) -> None:
        allowed = set(model.access_policy.allowed_connectors)
        denied = set(model.access_policy.denied_connectors)
        
        intersection = allowed.intersection(denied)
        if intersection:
            raise ValueError(
                f"Connectors cannot be both allowed and denied: {intersection}"
            )

    def _validate_execution(self, model: AgentDefinitionModel) -> None:
        if (
            model.execution.mode == ExecutionMode.single_step
            and model.execution.max_iterations > 1
        ):
            # This is technically allowed but logically inconsistent. 
            # We enforce consistency here.
            raise ValueError(
                "Execution mode 'single_step' cannot have 'max_iterations' > 1."
            )

    def _validate_output(self, model: AgentDefinitionModel) -> None:
        if (
            model.output.format == OutputFormat.json 
            and not model.output.json_schema
        ):
            # Strong suggestion becomes a rule to prevent runtime failures
            raise ValueError(
                "Output format 'json' requires 'json_schema' to be defined."
            )