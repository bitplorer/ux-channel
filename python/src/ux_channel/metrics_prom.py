"""Compatibility shim — implementation: ``ux_channel.ops_dx.metrics_prom``.

Stable: ``from ux_channel.metrics_prom import ...``
Preferred package path: ``ux_channel.ops_dx.metrics_prom``
"""
from __future__ import annotations

from ux_channel.ops_dx.metrics_prom import *  # noqa: F403
import ux_channel.ops_dx.metrics_prom as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
