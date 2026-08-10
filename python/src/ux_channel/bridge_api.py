"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_api``.

Stable: ``from ux_channel.bridge_api import ...``
Preferred package path: ``ux_channel.bridge_meta.bridge_api``
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_api import *  # noqa: F403
import ux_channel.bridge_meta.bridge_api as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
