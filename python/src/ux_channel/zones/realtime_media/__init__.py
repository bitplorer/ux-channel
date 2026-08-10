"""Zone: **realtime_media**

WebRTC / SFU / media — **optional realtime planes**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``webrtc`` — WebRTC signaling plane
* ``webrtc_http`` — WebRTC HTTP helpers
* ``webrtc_metrics`` — WebRTC metrics
* ``webrtc_turn`` — TURN credentials
* ``webrtc_ui`` — WebRTC plugin surface
* ``sfu`` — SFU adapter surface
* ``whip`` — WHIP/WHEP helpers
* ``media`` — Media plane + LiveKit DX
"""
from __future__ import annotations

ZONE = "realtime_media"
DESCRIPTION = 'WebRTC / SFU / media — **optional realtime planes**.'

MEMBERS: dict[str, str] = {
    'webrtc': 'WebRTC signaling plane',
    'webrtc_http': 'WebRTC HTTP helpers',
    'webrtc_metrics': 'WebRTC metrics',
    'webrtc_turn': 'TURN credentials',
    'webrtc_ui': 'WebRTC plugin surface',
    'sfu': 'SFU adapter surface',
    'whip': 'WHIP/WHEP helpers',
    'media': 'Media plane + LiveKit DX',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

