"""Compatibility shim — implementation: ``ux_channel.protocol.encode``.

Stable: ``from ux_channel.encode import ...``
Preferred package path: ``ux_channel.protocol.encode``
"""
from __future__ import annotations

from ux_channel.protocol.encode import *  # noqa: F403
import ux_channel.protocol.encode as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
