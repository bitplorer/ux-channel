"""Compatibility shim — implementation: ``ux_channel.transport.batch``.

Stable: ``from ux_channel.batch import ...``
Preferred package path: ``ux_channel.transport.batch``
"""
from __future__ import annotations

from ux_channel.transport.batch import *  # noqa: F403
import ux_channel.transport.batch as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
