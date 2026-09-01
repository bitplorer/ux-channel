"""Bridge package — contracts, scaffold, guest runtime (L4 plane).

Design
    Island integration without forking the Intent→Result loop: contracts and
    guest runtimes attach to the same Channel registry.

Architecture
    Singular ``bridge`` = machinery. Plural ``ux_channel.bridges`` = npm/fx/ui
    **presets** (prefer codegen over hand copies). Never on root ``__all__``.

Implementation
    Plane entry is ``attach_bridge``; scaffold/preset gen are tooling paths.
    Preferred::

        from ux_channel.bridge import attach_bridge
"""
from __future__ import annotations

from typing import Any

__all__ = ["attach_bridge", "BRIDGE_PUBLIC_API"]

# PEP 562 — importing ux_channel.bridge (e.g. factory → bridge.plugins)
# must not load bridge_plane. Public names stay identical.
_LAZY = {
    "attach_bridge": ("ux_channel.bridge.bridge_plane", "attach_bridge"),
    "BRIDGE_PUBLIC_API": ("ux_channel.bridge.bridge_plane", "BRIDGE_PUBLIC_API"),
}


def __getattr__(name: str) -> Any:
    spec = _LAZY.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    mod_name, attr = spec
    val = getattr(importlib.import_module(mod_name), attr)
    globals()[name] = val
    return val
