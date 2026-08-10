"""Compatibility shim — implementation: ``ux_channel.host.planes``.

Stable: ``from ux_channel.planes import ...``
Preferred package path: ``ux_channel.host.planes``
"""
from __future__ import annotations

from ux_channel.host.planes import *  # noqa: F403
import ux_channel.host.planes as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
