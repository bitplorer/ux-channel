"""Compatibility shim — implementation: ``ux_channel.host.recipes``.

Stable: ``from ux_channel.recipes import ...``
Preferred package path: ``ux_channel.host.recipes``
"""
from __future__ import annotations

from ux_channel.host.recipes import *  # noqa: F403
import ux_channel.host.recipes as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
