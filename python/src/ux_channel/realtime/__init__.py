"""Cohesive package: **realtime**

WebRTC / SFU / media optional plane.

Modules: media, sfu, webrtc, webrtc_http, webrtc_metrics, webrtc_turn, webrtc_ui, whip

Import: ``from ux_channel.realtime.MODULE import Symbol``
Public apps: ``from ux_channel.api import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['media', 'sfu', 'webrtc', 'webrtc_http', 'webrtc_metrics', 'webrtc_turn', 'webrtc_ui', 'whip']
PACKAGE = 'realtime'
__all__ = ["MEMBERS", "PACKAGE"]
