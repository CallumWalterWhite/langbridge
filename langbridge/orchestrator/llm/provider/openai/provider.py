

from typing import Any

from ..base import LLMProvider, LLMProviderName, ProviderConfigurationError
from ..factory import register_provider

try:  # pragma: no cover - optional dependency
    from langchain_openai import ChatOpenAI
except ImportError as exc:  # pragma: no cover - optional dependency
    ChatOpenAI = None  # type: ignore[assignment]
    _IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - optional dependency
    _IMPORT_ERROR = None

_ALLOWED_CONFIG_KEYS = {
    "temperature",
    "timeout",
    "max_retries",
    "max_tokens",
    "base_url",
    "organization",
    "default_headers",
    "http_client",
}


@register_provider
class OpenAIProvider(LLMProvider):
    name = LLMProviderName.OPENAI

    def create_chat_model(self, **overrides: Any):
        if ChatOpenAI is None:  # pragma: no cover - optional dependency
            raise ProviderConfigurationError(str(_IMPORT_ERROR))

        params = {key: self.configuration.get(key) for key in _ALLOWED_CONFIG_KEYS if key in self.configuration}
        params.update(overrides)
        params = self._clean_kwargs(params)
        params.setdefault("model", self.model_name)
        params.setdefault("api_key", self.api_key)

        return ChatOpenAI(**params)


__all__ = ["OpenAIProvider"]

