"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_style``.

Stable: ``from ux_channel.bridge_style import ...``
Preferred package path: ``ux_channel.bridge_meta.bridge_style``
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_style import *  # noqa: F403
import ux_channel.bridge_meta.bridge_style as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
