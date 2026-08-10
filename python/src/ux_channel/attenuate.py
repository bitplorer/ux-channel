"""Compatibility shim — implementation: ``ux_channel.security_plane.attenuate``.

Stable: ``from ux_channel.attenuate import ...``
Preferred package path: ``ux_channel.security_plane.attenuate``
"""
from __future__ import annotations

from ux_channel.security_plane.attenuate import *  # noqa: F403
import ux_channel.security_plane.attenuate as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
