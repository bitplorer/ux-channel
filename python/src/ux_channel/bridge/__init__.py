"""Bridge package — contracts, scaffold, guest runtime.

npm island presets live under ``ux_channel.bridges`` (plural).

Preferred::

    from ux_channel.bridge import attach_bridge
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.bridge.bridge_plane import BRIDGE_PUBLIC_API, attach_bridge

PACKAGE = "bridge"
__all__ = ["PACKAGE", "attach_bridge", "BRIDGE_PUBLIC_API"]
