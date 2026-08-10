"""Compatibility shim — implementation: ``ux_channel.realtime.webrtc_ui``.

Stable: ``from ux_channel.webrtc_ui import ...``
Preferred package path: ``ux_channel.realtime.webrtc_ui``
"""
from __future__ import annotations

from ux_channel.realtime.webrtc_ui import *  # noqa: F403
import ux_channel.realtime.webrtc_ui as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
