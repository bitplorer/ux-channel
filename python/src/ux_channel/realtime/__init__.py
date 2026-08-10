"""Cohesive package: **realtime**

Modules: media, sfu, webrtc, webrtc_http, webrtc_metrics, webrtc_turn, webrtc_ui, whip

Import: ``from ux_channel.realtime.MODULE import Symbol``
Legacy: ``from ux_channel.MODULE import Symbol`` (shim at top-level).
"""
from __future__ import annotations

MEMBERS = ['media', 'sfu', 'webrtc', 'webrtc_http', 'webrtc_metrics', 'webrtc_turn', 'webrtc_ui', 'whip']
PACKAGE = 'realtime'
__all__ = ["MEMBERS", "PACKAGE"]
