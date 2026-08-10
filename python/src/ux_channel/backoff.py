"""Compatibility shim — implementation: ``ux_channel.transport.backoff``.

Stable: ``from ux_channel.backoff import ...``
Preferred package path: ``ux_channel.transport.backoff``
"""
from __future__ import annotations

from ux_channel.transport.backoff import *  # noqa: F403
import ux_channel.transport.backoff as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
