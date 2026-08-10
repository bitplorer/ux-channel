"""Compatibility shim — implementation: ``ux_channel.ops_dx.dx_dashboard``.

Stable: ``from ux_channel.dx_dashboard import ...``
Preferred package path: ``ux_channel.ops_dx.dx_dashboard``
"""
from __future__ import annotations

from ux_channel.ops_dx.dx_dashboard import *  # noqa: F403
import ux_channel.ops_dx.dx_dashboard as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
