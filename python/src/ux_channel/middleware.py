"""Compatibility shim — implementation: ``ux_channel.transport.middleware``.

Stable: ``from ux_channel.middleware import ...``
Preferred package path: ``ux_channel.transport.middleware``
"""
from __future__ import annotations

from ux_channel.transport.middleware import *  # noqa: F403
import ux_channel.transport.middleware as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
