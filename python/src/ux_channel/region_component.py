"""Compatibility shim — implementation: ``ux_channel.host.region_component``.

Stable: ``from ux_channel.region_component import ...``
Preferred package path: ``ux_channel.host.region_component``
"""
from __future__ import annotations

from ux_channel.host.region_component import *  # noqa: F403
import ux_channel.host.region_component as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
