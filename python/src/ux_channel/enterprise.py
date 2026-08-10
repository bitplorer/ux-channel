"""Compatibility shim — implementation: ``ux_channel.ops_dx.enterprise``.

Stable: ``from ux_channel.enterprise import ...``
Preferred package path: ``ux_channel.ops_dx.enterprise``
"""
from __future__ import annotations

from ux_channel.ops_dx.enterprise import *  # noqa: F403
import ux_channel.ops_dx.enterprise as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
