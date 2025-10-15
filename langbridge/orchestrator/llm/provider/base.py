from abc import ABC
from enum import Enum

class LLMProviderName(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"

class LLMProvider(ABC):
    """Base class for LLM providers."""
    name: LLMProviderName

    def __init__(self, name: LLMProviderName):
        self.name = name

    def get_model(self, model_name: str) -> str:
        """Get the model name for the given model name."""
        return model_name

    def get_configuration(self, configuration: dict) -> dict:
        """Get the configuration for the given configuration."""
        return configuration