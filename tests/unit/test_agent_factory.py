import pytest
from langbridge.orchestrator.definitions.factory import AgentDefinitionFactory
from langbridge.orchestrator.definitions.model import (
    MemoryStrategy, ExecutionMode, ResponseMode, OutputFormat, LogLevel
)

def get_base_valid_definition():
    return {
        "prompt": {
            "system_prompt": "You are a helpful assistant."
        },
        "memory": {
            "strategy": "none"
        },
        "execution": {
            "mode": "single_step",
            "response_mode": "chat",
            "max_iterations": 1  # Valid for single_step
        },
        "output": {
            "format": "text"
        },
        "observability": {
            "log_level": "info",
            "emit_traces": True,
            "capture_prompts": True
        }
    }

def test_valid_creation():
    factory = AgentDefinitionFactory()
    definition = get_base_valid_definition()
    model = factory.create_agent_definition(definition)
    assert model.prompt.system_prompt == "You are a helpful assistant."

def test_invalid_memory_vector():
    factory = AgentDefinitionFactory()
    definition = get_base_valid_definition()
    definition["memory"] = {"strategy": "vector"} # Missing vector_index
    
    with pytest.raises(ValueError, match="Memory strategy 'vector' requires 'vector_index'"):
        factory.create_agent_definition(definition)

def test_invalid_memory_transient():
    factory = AgentDefinitionFactory()
    definition = get_base_valid_definition()
    definition["memory"] = {"strategy": "transient"} # Missing ttl_seconds
    
    with pytest.raises(ValueError, match="Memory strategy 'transient' requires 'ttl_seconds'"):
        factory.create_agent_definition(definition)

def test_invalid_execution_single_step_iterations():
    factory = AgentDefinitionFactory()
    definition = get_base_valid_definition()
    definition["execution"]["mode"] = "single_step"
    definition["execution"]["max_iterations"] = 5
    
    with pytest.raises(ValueError, match="Execution mode 'single_step' cannot have 'max_iterations' > 1"):
        factory.create_agent_definition(definition)

def test_invalid_output_json_schema():
    factory = AgentDefinitionFactory()
    definition = get_base_valid_definition()
    definition["output"]["format"] = "json"
    # Missing json_schema
    
    with pytest.raises(ValueError, match="Output format 'json' requires 'json_schema'"):
        factory.create_agent_definition(definition)
