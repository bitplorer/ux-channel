"""Compatibility shim — implementation: ``ux_channel.foundations.io_channel``.

Stable: ``from ux_channel.io_channel import ...``
Preferred package path: ``ux_channel.foundations.io_channel``
"""
from __future__ import annotations

from ux_channel.foundations.io_channel import *  # noqa: F403
import ux_channel.foundations.io_channel as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
