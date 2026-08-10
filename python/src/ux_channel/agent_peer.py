"""Compatibility shim — implementation: ``ux_channel.ops_dx.agent_peer``.

Stable: ``from ux_channel.agent_peer import ...``
Preferred package path: ``ux_channel.ops_dx.agent_peer``
"""
from __future__ import annotations

from ux_channel.ops_dx.agent_peer import *  # noqa: F403
import ux_channel.ops_dx.agent_peer as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
