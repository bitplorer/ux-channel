"""Compatibility shim — implementation: ``ux_channel.paint.render``.

Stable: ``from ux_channel.render import ...``
Preferred package path: ``ux_channel.paint.render``
"""
from __future__ import annotations

from ux_channel.paint.render import *  # noqa: F403
import ux_channel.paint.render as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
