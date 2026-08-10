"""Compatibility shim — implementation: ``ux_channel.host.region_cli``.

Stable: ``from ux_channel.region_cli import ...``
Preferred package path: ``ux_channel.host.region_cli``
"""
from __future__ import annotations

from ux_channel.host.region_cli import *  # noqa: F403
import ux_channel.host.region_cli as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
