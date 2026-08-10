"""Compatibility shim — implementation: ``ux_channel.realtime.webrtc_turn``.

Stable: ``from ux_channel.webrtc_turn import ...``
Preferred package path: ``ux_channel.realtime.webrtc_turn``
"""
from __future__ import annotations

from ux_channel.realtime.webrtc_turn import *  # noqa: F403
import ux_channel.realtime.webrtc_turn as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
