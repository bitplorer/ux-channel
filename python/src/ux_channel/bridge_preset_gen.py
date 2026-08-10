"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_preset_gen``.

Stable: ``from ux_channel.bridge_preset_gen import ...``
Preferred package path: ``ux_channel.bridge_meta.bridge_preset_gen``
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_preset_gen import *  # noqa: F403
import ux_channel.bridge_meta.bridge_preset_gen as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
