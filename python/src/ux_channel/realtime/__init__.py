"""Realtime — WebRTC, SFU, media placement (L4 plane).

Design
    Optional product plane for live media. Same Channel/trust story; never a
    second action registry.

Architecture
    L4 — must not appear on root ``__all__``. Defaults fail closed (tickets,
    origins) per production hardening.

Implementation
    Preferred::

        from ux_channel.realtime import media, webrtc
"""
from __future__ import annotations

from . import media, webrtc

__all__ = ["media", "webrtc"]
