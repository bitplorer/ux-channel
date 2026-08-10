"""
WHIP / WHEP-inspired HTTP helpers for uxchannel (optional plane).

First principles
----------------
* **WHIP** (WebRTC-HTTP Ingestion Protocol): publisher POSTs an SDP *offer*;
  the server (or SFU) returns an SDP *answer*.
* **WHEP** (egress): viewer POSTs; receives media description to play.

uxchannel does **not** implement a media SFU. These helpers:

1. Validate SDP-ish bodies
2. Park offers in the shared :func:`get_rtc_store` so a second party can answer
3. Power optional routes when ``ChannelConfig.whip_enabled=True``

For real broadcast at scale, use :mod:`ux_channel.sfu` (e.g. LiveKit).

Intended usage
--------------
::

    from ux_channel.realtime.whip import parse_sdp_body, is_sdp_offer, whip_enabled

    if whip_enabled(cfg):
        sdp = parse_sdp_body(await request.body())
        ...
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "whip_enabled",
    "parse_sdp_body",
    "is_sdp_offer",
    "normalize_sdp_json",
]


def whip_enabled(config: Any) -> bool:
    """Return True when WHIP/WHEP routes should be mounted."""
    if config is None:
        return False
    return bool(getattr(config, "whip_enabled", False))


def parse_sdp_body(raw: bytes | str | None) -> str:
    """Decode request body to an SDP string (UTF-8, lossy on bad bytes)."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").strip()
    return str(raw).strip()


def is_sdp_offer(sdp: str) -> bool:
    """
    Heuristic: body looks like SDP with a media section.

    Not a full SDP parser — rejects empty / non-SDP noise early.
    """
    if not sdp or "v=0" not in sdp:
        return False
    return "m=" in sdp


def normalize_sdp_json(body: dict[str, Any]) -> str:
    """Extract SDP from JSON ``{ \"sdp\": \"...\", \"type\": \"offer\" }``."""
    if not isinstance(body, dict):
        return ""
    return str(body.get("sdp") or "").strip()
