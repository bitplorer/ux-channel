"""Compatibility shim — implementation: ``ux_channel.host.registry``.

Stable: ``from ux_channel.registry import ...``
Preferred package path: ``ux_channel.host.registry``
"""
from __future__ import annotations

from ux_channel.host.registry import *  # noqa: F403
import ux_channel.host.registry as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
