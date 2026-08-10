"""Compatibility shim — implementation: ``ux_channel.host.catalog``.

Stable: ``from ux_channel.catalog import ...``
Preferred package path: ``ux_channel.host.catalog``
"""
from __future__ import annotations

from ux_channel.host.catalog import *  # noqa: F403
import ux_channel.host.catalog as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
