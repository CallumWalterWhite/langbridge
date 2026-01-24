from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable
from types import ModuleType

from dependency_injector import containers

__all__ = ["import_submodules", "wire_packages"]


def import_submodules(package_name: str) -> ModuleType:
    """Import a package and all its submodules recursively."""
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        # It's a single module, not a package.
        return pkg

    prefix = f"{pkg.__name__}."
    for modinfo in pkgutil.walk_packages(pkg.__path__, prefix=prefix):
        importlib.import_module(modinfo.name)
    return pkg


def _unique_names(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def wire_packages(
    container: containers.DeclarativeContainer,
    package_names: Iterable[str],
    extra_modules: Iterable[str] = (),
    *,
    strict: bool = True,
) -> None:
    """
    Import & wire all submodules in the given packages.
    Optionally wire extra top-level modules by name (e.g., "main").
    """
    packages: list[ModuleType] = []
    for name in _unique_names(package_names):
        try:
            packages.append(import_submodules(name))
        except ModuleNotFoundError as exc:
            if strict:
                raise
            continue
        except Exception:
            if strict:
                raise

    modules: list[ModuleType] = []
    for name in _unique_names(extra_modules):
        try:
            modules.append(importlib.import_module(name))
        except ModuleNotFoundError:
            if strict:
                raise
        except Exception:
            if strict:
                raise

    container.wire(packages=packages, modules=modules)
