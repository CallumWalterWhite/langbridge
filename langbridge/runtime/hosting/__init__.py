from __future__ import annotations

from typing import Any

__all__ = [
    "create_runtime_api_app",
    "run_runtime_api",
]


def __getattr__(name: str) -> Any:
    if name == "create_runtime_api_app":
        from langbridge.runtime.hosting.app import create_runtime_api_app

        return create_runtime_api_app
    if name == "run_runtime_api":
        from langbridge.runtime.hosting.server import run_runtime_api

        return run_runtime_api
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
