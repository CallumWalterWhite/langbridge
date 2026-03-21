"""
Factory and registry helpers for orchestrator LLM providers.
"""
from typing import Any, Dict, Iterable, Type, TypeVar

try:  # pragma: no cover - optional dependency fallback
    from langchain_core.language_models import BaseChatModel
except Exception:  # pragma: no cover
    class BaseChatModel:  # type: ignore[no-redef]
        pass

from .base import (
    LLMConnectionConfig,
    LLMProvider,
    LLMProviderName,
    ProviderNotRegisteredError,
)

ProviderType = TypeVar("ProviderType", bound=LLMProvider)

_REGISTRY: Dict[LLMProviderName, Type[LLMProvider]] = {}


def register_provider(cls: Type[ProviderType]) -> Type[ProviderType]:
    if not issubclass(cls, LLMProvider):
        raise TypeError("Only subclasses of LLMProvider can be registered.")
    _REGISTRY[cls.name] = cls
    return cls


def get_provider_class(name: LLMProviderName) -> Type[LLMProvider]:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise ProviderNotRegisteredError(f"No provider registered for '{name.value}'.") from exc


def registered_providers() -> Iterable[LLMProviderName]:
    return tuple(_REGISTRY.keys())


def create_provider(connection: Any) -> LLMProvider:
    config = LLMConnectionConfig.from_connection(connection)
    provider_cls = get_provider_class(config.provider)
    return provider_cls(config)


def create_chat_model_from_connection(connection: Any, **overrides: Any) -> BaseChatModel:
    provider = create_provider(connection)
    return provider.create_chat_model(**overrides)


__all__ = [
    "register_provider",
    "get_provider_class",
    "registered_providers",
    "create_provider",
    "create_chat_model_from_connection",
]
