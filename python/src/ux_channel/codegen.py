"""Compatibility shim — implementation: ``ux_channel.ops_dx.codegen``.

Stable: ``from ux_channel.codegen import ...``
Preferred package path: ``ux_channel.ops_dx.codegen``
"""
from __future__ import annotations

from ux_channel.ops_dx.codegen import *  # noqa: F403
import ux_channel.ops_dx.codegen as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
