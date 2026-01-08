

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, MutableMapping, Union
from langchain_core.messages import BaseMessage

from langchain_core.language_models import BaseChatModel


class LLMProviderName(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"


class ProviderConfigurationError(ValueError):
    """Raised when an LLM provider receives invalid configuration."""


class ProviderNotRegisteredError(LookupError):
    """Raised when no provider implementation is registered for a name."""


def _extract_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def coerce_provider_name(value: Any) -> LLMProviderName:
    if isinstance(value, LLMProviderName):
        return value
    if hasattr(value, "value"):
        return LLMProviderName(str(value.value).lower())
    if isinstance(value, str):
        return LLMProviderName(value.lower())
    raise ProviderConfigurationError("Unsupported provider value supplied.")


@dataclass(frozen=True)
class LLMConnectionConfig:
    provider: LLMProviderName
    api_key: str
    model: str
    configuration: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_connection(cls, connection: Any) -> "LLMConnectionConfig":
        provider = coerce_provider_name(_extract_value(connection, "provider"))
        api_key = _extract_value(connection, "api_key")
        model = _extract_value(connection, "model")
        configuration = _extract_value(connection, "configuration", {}) or {}

        if api_key is None:
            raise ProviderConfigurationError("LLM connection is missing an API key.")
        if model is None:
            raise ProviderConfigurationError("LLM connection is missing a model identifier.")
        if not isinstance(configuration, MutableMapping):
            configuration = dict(configuration)
        else:
            configuration = dict(configuration.items())

        return cls(
            provider=provider,
            api_key=str(api_key),
            model=str(model),
            configuration=configuration,
        )


class LLMProvider(ABC):
    """Base class for LLM providers used by the orchestrator."""

    name: LLMProviderName

    def __init__(self, config: LLMConnectionConfig):
        if not isinstance(config, LLMConnectionConfig):
            raise ProviderConfigurationError("LLMProvider requires an LLMConnectionConfig instance.")
        if hasattr(self, "name") and config.provider != self.name:
            raise ProviderConfigurationError(
                f"Configuration mis-match: expected provider '{self.name.value}', "
                f"got '{config.provider.value}'."
            )
        self._config = config

    @property
    def config(self) -> LLMConnectionConfig:
        return self._config

    @property
    def api_key(self) -> str:
        return self._config.api_key

    @property
    def model_name(self) -> str:
        return self._config.model

    @property
    def configuration(self) -> dict[str, Any]:
        return dict(self._config.configuration)

    def _clean_kwargs(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in params.items() if v is not None}

    @abstractmethod
    def create_chat_model(self, **overrides: Any) -> BaseChatModel:
        """Instantiate a LangChain chat model for this provider."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a text completion for the given prompt."""

    @abstractmethod
    async def acomplete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Asynchronously generate a text completion for the given prompt."""

    @abstractmethod
    def invoke(
        self,
        messages: Union[list[dict[str, Any]], list[BaseMessage]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Union[dict[str, Any], BaseMessage]:
        """Invoke the model with a list of messages and return the raw response."""

    @abstractmethod
    async def ainvoke(
        self,
        messages: Union[list[dict[str, Any]], list[BaseMessage]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Union[dict[str, Any], BaseMessage]:
        """Asynchronously invoke the model with a list of messages and return the raw response."""
        
    @abstractmethod
    async def create_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Asynchronously create embeddings for a list of texts."""