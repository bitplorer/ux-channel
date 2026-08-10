"""Compatibility shim — implementation: ``ux_channel.security_plane.bulkhead``.

Stable: ``from ux_channel.bulkhead import ...``
Preferred package path: ``ux_channel.security_plane.bulkhead``
"""
from __future__ import annotations

from ux_channel.security_plane.bulkhead import *  # noqa: F403
import ux_channel.security_plane.bulkhead as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
