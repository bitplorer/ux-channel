"""Compatibility shim — implementation: ``ux_channel.ops_dx.explain``.

Stable: ``from ux_channel.explain import ...``
Preferred package path: ``ux_channel.ops_dx.explain``
"""
from __future__ import annotations

from ux_channel.ops_dx.explain import *  # noqa: F403
import ux_channel.ops_dx.explain as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
