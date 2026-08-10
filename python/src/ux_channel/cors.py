"""Compatibility shim — implementation: ``ux_channel.transport.cors``.

Stable: ``from ux_channel.cors import ...``
Preferred package path: ``ux_channel.transport.cors``
"""
from __future__ import annotations

from ux_channel.transport.cors import *  # noqa: F403
import ux_channel.transport.cors as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
