"""Compatibility shim — implementation: ``ux_channel.foundations.quantity``.

Stable: ``from ux_channel.quantity import ...``
Preferred package path: ``ux_channel.foundations.quantity``
"""
from __future__ import annotations

from ux_channel.foundations.quantity import *  # noqa: F403
import ux_channel.foundations.quantity as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
