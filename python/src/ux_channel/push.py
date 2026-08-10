"""Compatibility shim — implementation: ``ux_channel.transport.push``.

Stable: ``from ux_channel.push import ...``
Preferred package path: ``ux_channel.transport.push``
"""
from __future__ import annotations

from ux_channel.transport.push import *  # noqa: F403
import ux_channel.transport.push as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
