"""Cohesive package: **security_plane**

CSRF, attenuate, rate limits. Named _plane to avoid shadowing security.py.

Modules: attenuate, bulkhead, host_csrf, limits, policy, push_security, ratelimit, security, security_events, tree_cap, ws_security

Import: ``from ux_channel.security_plane.MODULE import Symbol``
Legacy: ``from ux_channel.MODULE import Symbol`` (generated alias).

Source of truth: PACKAGE_MAP.json · sync: scripts/sync_python_layout.py
"""
from __future__ import annotations

MEMBERS = ['attenuate', 'bulkhead', 'host_csrf', 'limits', 'policy', 'push_security', 'ratelimit', 'security', 'security_events', 'tree_cap', 'ws_security']
PACKAGE = 'security_plane'
__all__ = ["MEMBERS", "PACKAGE"]
