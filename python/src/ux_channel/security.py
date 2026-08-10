"""Compatibility shim — implementation: ``ux_channel.security_plane.security``.

Stable: ``from ux_channel.security import ...``
Preferred package path: ``ux_channel.security_plane.security``
"""
from __future__ import annotations

from ux_channel.security_plane.security import *  # noqa: F403
import ux_channel.security_plane.security as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
