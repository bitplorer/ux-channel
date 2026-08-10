"""Compatibility shim — implementation: ``ux_channel.paint.morph_ir``.

Stable: ``from ux_channel.morph_ir import ...``
Preferred package path: ``ux_channel.paint.morph_ir``
"""
from __future__ import annotations

from ux_channel.paint.morph_ir import *  # noqa: F403
import ux_channel.paint.morph_ir as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
