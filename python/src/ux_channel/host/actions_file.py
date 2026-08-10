"""File-based action discovery — plug-and-play action modules."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Callable

from ux_channel.host.registry import ActionRegistry


def action(name: str | None = None) -> Callable:
    """Mark a function as a Channel action for file discovery."""

    def deco(fn: Callable) -> Callable:
        fn.__ux_action__ = name or fn.__name__  # type: ignore[attr-defined]
        return fn

    return deco


def load_actions_from_package(
    registry: ActionRegistry,
    package: str,
    *,
    prefix: str = "",
) -> list[str]:
    """
    Import package (and submodules if package) and register @action-marked callables.
    """
    pkg = importlib.import_module(package)
    registered: list[str] = []
    registered.extend(_register_module(registry, pkg, prefix))
    paths = getattr(pkg, "__path__", None)
    if not paths:
        return registered
    for mod in pkgutil.walk_packages(paths, prefix=package + "."):
        if mod.ispkg:
            continue
        m = importlib.import_module(mod.name)
        registered.extend(_register_module(registry, m, prefix))
    return registered


def _register_module(registry: ActionRegistry, mod: Any, prefix: str) -> list[str]:
    out: list[str] = []
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        an = getattr(obj, "__ux_action__", None)
        if an is None:
            continue
        full = an if "." in str(an) else f"{prefix}{an}" if prefix else str(an)
        if full in registry.names():
            registry.replace(full, obj)
        else:
            registry.register(full, obj)
        out.append(full)
    return out
