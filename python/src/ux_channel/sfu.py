"""Compatibility shim — implementation: ``ux_channel.realtime.sfu``.

Stable: ``from ux_channel.sfu import ...``
Preferred package path: ``ux_channel.realtime.sfu``
"""
from __future__ import annotations

from ux_channel.realtime.sfu import *  # noqa: F403
import ux_channel.realtime.sfu as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
