"""Security package — CSRF, limits, attenuation, rate limits (L2/L3).

Design
    Policy helpers that sit beside caps: CSRF headers, arg attenuation, rate
    limits, WS/push security. Caps remain in protocol; this package does not
    reimplement CapService.

Architecture
    Host dispatch may call into these modules; nothing here should invent a
    second Intent trust story.

Implementation
    Preferred public names::

        from ux_channel.security import intent_headers, attenuate, safe_href
"""
from __future__ import annotations

from ux_channel.security.attenuate import attenuate
from ux_channel.security.host_csrf import intent_headers
from ux_channel.security.security import safe_href

__all__ = ["intent_headers", "attenuate", "safe_href"]
