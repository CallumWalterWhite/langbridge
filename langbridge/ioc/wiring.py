# wiring.py
import importlib
import pkgutil
from types import ModuleType
from typing import Iterable, List

from dependency_injector import containers


def import_submodules(package_name: str) -> ModuleType:
    """Import a package and all its submodules recursively."""
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        # It's a single module, not a package
        return pkg

    prefix = pkg.__name__ + "."
    for modinfo in pkgutil.walk_packages(pkg.__path__, prefix=prefix):
        importlib.import_module(modinfo.name)
    return pkg


def wire_packages(container: containers.DeclarativeContainer, package_names: Iterable[str], extra_modules: Iterable[str] = ()):
    """
    Import & wire all submodules in the given packages.
    Optionally wire some extra top-level modules by name (e.g., "main").
    """
    packages: List[ModuleType] = []
    for name in package_names:
        packages.append(import_submodules(name))

    modules: List[ModuleType] = []
    for name in extra_modules:
        modules.append(importlib.import_module(name))

    # Wire everything
    container.wire(packages=packages, modules=modules)
