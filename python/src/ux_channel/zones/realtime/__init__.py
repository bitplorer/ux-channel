"""Zone / package: **realtime**

WebRTC / SFU / media planes.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'realtime'
DESCRIPTION = 'WebRTC / SFU / media planes.'
MEMBERS = {'media': 'Media plane bridge — mesh + battle-tested SFU (LiveKit) as one DX.', 'sfu': 'SFU adapter surface (P2) — pluggable bridge to external media servers.', 'webrtc': 'WebRTC peer-to-peer **signaling** plane for ux-channel.', 'webrtc_http': 'HTTP helpers for the WebRTC plane — keep FastAPI routes thin.', 'webrtc_metrics': 'In-process WebRTC signaling metrics (P1).', 'webrtc_turn': 'Short-lived TURN credentials (coturn REST / static-auth-secret).', 'webrtc_ui': 'WebRTC **plugin** surface — framework-agnostic, no UI chrome.', 'whip': 'WHIP / WHEP-inspired HTTP helpers for uxchannel (optional plane).'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
