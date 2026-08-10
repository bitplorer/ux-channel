"""Compatibility shim — implementation: ``ux_channel.security_plane.policy``.

Stable: ``from ux_channel.policy import ...``
Preferred package path: ``ux_channel.security_plane.policy``
"""
from __future__ import annotations

from ux_channel.security_plane.policy import *  # noqa: F403
import ux_channel.security_plane.policy as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
