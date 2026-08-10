"""Compatibility shim — implementation: ``ux_channel.realtime.webrtc_http``.

Stable: ``from ux_channel.webrtc_http import ...``
Preferred package path: ``ux_channel.realtime.webrtc_http``
"""
from __future__ import annotations

from ux_channel.realtime.webrtc_http import *  # noqa: F403
import ux_channel.realtime.webrtc_http as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
