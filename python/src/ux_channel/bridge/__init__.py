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

from ux_channel.bridge.bridge_plane import BRIDGE_PUBLIC_API, attach_bridge

__all__ = ["attach_bridge", "BRIDGE_PUBLIC_API"]
