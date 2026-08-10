"""Compatibility shim — implementation: ``ux_channel.ops_dx.intent_log``.

Stable: ``from ux_channel.intent_log import ...``
Preferred package path: ``ux_channel.ops_dx.intent_log``
"""
from __future__ import annotations

from ux_channel.ops_dx.intent_log import *  # noqa: F403
import ux_channel.ops_dx.intent_log as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
