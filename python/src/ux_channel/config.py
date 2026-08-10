"""Compatibility shim — implementation: ``ux_channel.host.config``.

Stable: ``from ux_channel.config import ...``
Preferred package path: ``ux_channel.host.config``
"""
from __future__ import annotations

from ux_channel.host.config import *  # noqa: F403
import ux_channel.host.config as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
