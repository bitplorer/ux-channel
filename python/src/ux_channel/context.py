"""Compatibility shim — implementation: ``ux_channel.host.context``.

Stable: ``from ux_channel.context import ...``
Preferred package path: ``ux_channel.host.context``
"""
from __future__ import annotations

from ux_channel.host.context import *  # noqa: F403
import ux_channel.host.context as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
