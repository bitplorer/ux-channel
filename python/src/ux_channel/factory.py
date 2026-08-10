"""Compatibility shim — implementation: ``ux_channel.host.factory``.

Stable: ``from ux_channel.factory import ...``
Preferred package path: ``ux_channel.host.factory``
"""
from __future__ import annotations

from ux_channel.host.factory import *  # noqa: F403
import ux_channel.host.factory as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
