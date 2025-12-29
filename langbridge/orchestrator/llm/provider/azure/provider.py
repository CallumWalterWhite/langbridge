

from typing import Any

from ..base import LLMProvider, LLMProviderName, ProviderConfigurationError
from ..factory import register_provider

try:  # pragma: no cover - optional dependency
    from langchain_openai import AzureChatOpenAI
    from langchain_core.messages import BaseMessage
except ImportError as exc:  # pragma: no cover - optional dependency
    AzureChatOpenAI = None  # type: ignore[assignment]
    if hasattr(exc, "add_note"):
        exc.add_note("Install 'langchain-openai' to enable the Azure OpenAI provider.")
    _IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - optional dependency
    _IMPORT_ERROR = None

_OPTIONAL_CONFIG_KEYS = {
    "temperature",
    "timeout",
    "max_retries",
    "max_tokens",
    "default_headers",
    "http_client",
}


@register_provider
class AzureOpenAIProvider(LLMProvider):
    name = LLMProviderName.AZURE

    def create_chat_model(self, **overrides: Any):
        if AzureChatOpenAI is None:  # pragma: no cover - optional dependency
            raise ProviderConfigurationError(str(_IMPORT_ERROR))

        deployment = (
            self.configuration.get("deployment_name")
            or self.configuration.get("deployment")
            or self.configuration.get("azure_deployment")
        )
        if not deployment:
            raise ProviderConfigurationError(
                "Azure OpenAI configuration requires 'deployment_name' "
                "(or 'deployment'/'azure_deployment')."
            )

        endpoint = (
            self.configuration.get("azure_endpoint")
            or self.configuration.get("api_base")
            or self.configuration.get("endpoint")
        )
        if not endpoint:
            raise ProviderConfigurationError(
                "Azure OpenAI configuration requires 'azure_endpoint' "
                "(or 'api_base'/'endpoint')."
            )

        api_version = overrides.pop("api_version", None) or self.configuration.get("api_version") or "2024-05-01-preview"

        params = {
            "api_key": self.api_key,
            "azure_deployment": deployment,
            "azure_endpoint": endpoint,
            "api_version": api_version,
            "model": self.model_name,
        }

        for key in _OPTIONAL_CONFIG_KEYS:
            if key in self.configuration:
                params[key] = self.configuration[key]

        params.update(overrides)
        params = self._clean_kwargs(params)

        return AzureChatOpenAI(**params)
    
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        chat_model = self.create_chat_model(temperature=temperature, max_tokens=max_tokens)
        response = chat_model.predict_messages([BaseMessage(content=prompt)])
        return str(response.content)


__all__ = ["AzureOpenAIProvider"]
