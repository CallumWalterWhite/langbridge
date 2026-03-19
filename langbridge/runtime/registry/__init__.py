"""Compatibility wrapper for the pre-convergence runtime registry namespace."""

from langbridge.runtime.bootstrap import (  # noqa: F401
    build_hosted_runtime,
    build_local_runtime,
)

__all__ = ["build_hosted_runtime", "build_local_runtime"]
