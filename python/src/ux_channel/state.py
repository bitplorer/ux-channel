"""Compatibility shim — implementation: ``ux_channel.host.state``.

Stable: ``from ux_channel.state import ...``
Preferred package path: ``ux_channel.host.state``
"""
from __future__ import annotations

from ux_channel.host.state import *  # noqa: F403
import ux_channel.host.state as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
