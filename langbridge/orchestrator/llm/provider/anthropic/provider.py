

from typing import Any

from ..base import LLMProvider, LLMProviderName, ProviderConfigurationError
from ..factory import register_provider

try:  # pragma: no cover - optional dependency
    from langchain_anthropic import ChatAnthropic
except ImportError as exc:  # pragma: no cover - optional dependency
    ChatAnthropic = None  # type: ignore[assignment]
    if hasattr(exc, "add_note"):
        exc.add_note("Install 'langchain-anthropic' to enable the Anthropic provider.")
    _IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - optional dependency
    _IMPORT_ERROR = None

_ALLOWED_CONFIG_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "timeout",
    "max_retries",
    "default_headers",
    "http_client",
    "stop_sequences",
    "metadata",
    "response_format",
}


@register_provider
class AnthropicProvider(LLMProvider):
    name = LLMProviderName.ANTHROPIC

    def create_chat_model(self, **overrides: Any):
        if ChatAnthropic is None:  # pragma: no cover - optional dependency
            raise ProviderConfigurationError(str(_IMPORT_ERROR))

        params = {key: self.configuration.get(key) for key in _ALLOWED_CONFIG_KEYS if key in self.configuration}
        params.update(overrides)
        params = self._clean_kwargs(params)
        params.setdefault("model", self.model_name)
        params.setdefault("api_key", self.api_key)

        # Align optional token settings with Anthropic defaults.
        if "max_output_tokens" not in params:
            max_tokens = self.configuration.get("max_output_tokens") or self.configuration.get("max_tokens")
            params["max_output_tokens"] = max_tokens if max_tokens is not None else 1024

        return ChatAnthropic(**params)


__all__ = ["AnthropicProvider"]
