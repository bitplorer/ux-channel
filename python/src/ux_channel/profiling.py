"""Compatibility shim — implementation: ``ux_channel.ops_dx.profiling``.

Stable: ``from ux_channel.profiling import ...``
Preferred package path: ``ux_channel.ops_dx.profiling``
"""
from __future__ import annotations

from ux_channel.ops_dx.profiling import *  # noqa: F403
import ux_channel.ops_dx.profiling as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
