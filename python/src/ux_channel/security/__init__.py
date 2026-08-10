"""Security package — CSRF, limits, attenuation, rate limits.

Preferred::

    from ux_channel.security import intent_headers, attenuate, safe_href
"""
from __future__ import annotations

from ux_channel.security.attenuate import attenuate
from ux_channel.security.host_csrf import intent_headers
from ux_channel.security.security import safe_href

PACKAGE = "security"
__all__ = ["PACKAGE", "intent_headers", "attenuate", "safe_href"]
