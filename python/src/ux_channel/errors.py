"""Compatibility shim — implementation: ``ux_channel.protocol.errors``.

Stable: ``from ux_channel.errors import ...``
Preferred package path: ``ux_channel.protocol.errors``
"""
from __future__ import annotations

from ux_channel.protocol.errors import *  # noqa: F403
import ux_channel.protocol.errors as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
