"""Compatibility shim — implementation: ``ux_channel.ops_dx.pydantic_actions``.

Stable: ``from ux_channel.pydantic_actions import ...``
Preferred package path: ``ux_channel.ops_dx.pydantic_actions``
"""
from __future__ import annotations

from ux_channel.ops_dx.pydantic_actions import *  # noqa: F403
import ux_channel.ops_dx.pydantic_actions as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
