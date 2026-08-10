"""Zone: **security**

CSRF, attenuate, limits, auth doors — **authority hardening**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``host_csrf`` — CSRF forwarding / channel CSRF
* ``security`` — HTTP + apply-op security helpers
* ``security_events`` — Structured security event stream
* ``attenuate`` — Cap attenuation (narrow only)
* ``tree_cap`` — Capability-shaped document trees
* ``policy`` — Optional allow/deny hooks
* ``push_security`` — SSE/push subscribe auth
* ``ws_security`` — WebSocket auth doors
* ``ratelimit`` — Action rate limits
* ``bulkhead`` — Concurrency bulkhead
* ``limits`` — Result size limits
"""
from __future__ import annotations

ZONE = "security"
DESCRIPTION = 'CSRF, attenuate, limits, auth doors — **authority hardening**.'

MEMBERS: dict[str, str] = {
    'host_csrf': 'CSRF forwarding / channel CSRF',
    'security': 'HTTP + apply-op security helpers',
    'security_events': 'Structured security event stream',
    'attenuate': 'Cap attenuation (narrow only)',
    'tree_cap': 'Capability-shaped document trees',
    'policy': 'Optional allow/deny hooks',
    'push_security': 'SSE/push subscribe auth',
    'ws_security': 'WebSocket auth doors',
    'ratelimit': 'Action rate limits',
    'bulkhead': 'Concurrency bulkhead',
    'limits': 'Result size limits',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

