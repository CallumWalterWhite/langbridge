

from typing import Any, Union

from ..base import LLMProvider, LLMProviderName, ProviderConfigurationError
from ..factory import register_provider

try:  # pragma: no cover - optional dependency
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import BaseMessage
except ImportError as exc:  # pragma: no cover - optional dependency
    ChatOpenAI = None  # type: ignore[assignment]
    HumanMessage = None  # type: ignore[assignment]
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

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        chat_model = self.create_chat_model(temperature=temperature, max_tokens=max_tokens)
        response = chat_model.invoke(prompt)
        if isinstance(response, BaseMessage):
            return str(response.content)
        return str(response)
    
    async def acomplete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        chat_model = self.create_chat_model(temperature=temperature, max_tokens=max_tokens)
        response = await chat_model.ainvoke(prompt)
        if isinstance(response, BaseMessage):
            return str(response.content)
        return str(response)
    
    def invoke(
        self,
        messages: Union[list[dict[str, Any]], list[BaseMessage]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Union[dict[str, Any], BaseMessage]:
        chat_model = self.create_chat_model(temperature=temperature, max_tokens=max_tokens)
        response = chat_model.invoke(messages)
        return response
    
    async def ainvoke(
        self,
        messages: Union[list[dict[str, Any]], list[BaseMessage]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Union[dict[str, Any], BaseMessage]:
        chat_model = self.create_chat_model(temperature=temperature, max_tokens=max_tokens)
        response = await chat_model.ainvoke(messages)
        return response
    
    async def create_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if ChatOpenAI is None:  # pragma: no cover - optional dependency
            raise ProviderConfigurationError(str(_IMPORT_ERROR))
        
        from langchain.embeddings.openai import OpenAIEmbeddings

        if not texts:
            return []

        embedding_model = (
            self.configuration.get("embedding_model")
            or self.configuration.get("embedding_deployment")
            or self.configuration.get("embedding")
            or "text-embedding-3-small"
        )
        params = {key: self.configuration.get(key) for key in _ALLOWED_CONFIG_KEYS if key in self.configuration}
        params = self._clean_kwargs(params)
        params.setdefault("model", embedding_model)
        params.setdefault("api_key", self.api_key)

        embedding_model = OpenAIEmbeddings(**params)
        embeddings = await embedding_model.aembed_documents(texts)
        return embeddings

__all__ = ["OpenAIProvider"]
