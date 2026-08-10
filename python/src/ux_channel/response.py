"""Compatibility shim — implementation: ``ux_channel.paint.response``.

Stable: ``from ux_channel.response import ...``
Preferred package path: ``ux_channel.paint.response``
"""
from __future__ import annotations

from ux_channel.paint.response import *  # noqa: F403
import ux_channel.paint.response as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
