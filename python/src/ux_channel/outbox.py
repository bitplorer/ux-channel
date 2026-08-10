"""Compatibility shim — implementation: ``ux_channel.transport.outbox``.

Stable: ``from ux_channel.outbox import ...``
Preferred package path: ``ux_channel.transport.outbox``
"""
from __future__ import annotations

from ux_channel.transport.outbox import *  # noqa: F403
import ux_channel.transport.outbox as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
