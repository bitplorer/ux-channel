"""Compatibility shim — implementation: ``ux_channel.transport.ws_protocol``.

Stable: ``from ux_channel.ws_protocol import ...``
Preferred package path: ``ux_channel.transport.ws_protocol``
"""
from __future__ import annotations

from ux_channel.transport.ws_protocol import *  # noqa: F403
import ux_channel.transport.ws_protocol as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
