"""Cohesive package: **security**

CSRF, attenuate, rate limits.

Modules: attenuate, bulkhead, host_csrf, limits, policy, push_security, ratelimit, security, security_events, tree_cap, ws_security

Import: ``from ux_channel.security.MODULE import Symbol``
Public apps: ``from ux_channel.api import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['attenuate', 'bulkhead', 'host_csrf', 'limits', 'policy', 'push_security', 'ratelimit', 'security', 'security_events', 'tree_cap', 'ws_security']
PACKAGE = 'security'
__all__ = ["MEMBERS", "PACKAGE"]
