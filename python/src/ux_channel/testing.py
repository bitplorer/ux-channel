"""Compatibility shim — implementation: ``ux_channel.host.testing``.

Stable: ``from ux_channel.testing import ...``
Preferred package path: ``ux_channel.host.testing``
"""
from __future__ import annotations

from ux_channel.host.testing import *  # noqa: F403
import ux_channel.host.testing as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
