"""Compatibility shim — implementation: ``ux_channel.security_plane.limits``.

Stable: ``from ux_channel.limits import ...``
Preferred package path: ``ux_channel.security_plane.limits``
"""
from __future__ import annotations

from ux_channel.security_plane.limits import *  # noqa: F403
import ux_channel.security_plane.limits as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
