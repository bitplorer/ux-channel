"""Zone: **transport**

ASGI, push, WS, batch — **how Intents arrive**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``asgi`` — SUBPACKAGE: HTTP/ASGI adapters
* ``batch`` — Batch Intent dispatch
* ``stream`` — SSE progressive Results
* ``push`` — Server push bus
* ``cors`` — CORS helper
* ``middleware`` — ASGI middleware helpers
* ``ws_protocol`` — WebSocket message helpers
* ``ws_limits`` — WebSocket rate limits
* ``backoff`` — Retry backoff strategies
* ``concurrency`` — Internal parallel dispatch
* ``outbox`` — Intent outbox queue
* ``intent_sync`` — Cross-worker intent sync
* ``redis_extra`` — SUBPACKAGE: Redis stores (optional)
"""
from __future__ import annotations

ZONE = "transport"
DESCRIPTION = 'ASGI, push, WS, batch — **how Intents arrive**.'

MEMBERS: dict[str, str] = {
    'asgi': 'SUBPACKAGE: HTTP/ASGI adapters',
    'batch': 'Batch Intent dispatch',
    'stream': 'SSE progressive Results',
    'push': 'Server push bus',
    'cors': 'CORS helper',
    'middleware': 'ASGI middleware helpers',
    'ws_protocol': 'WebSocket message helpers',
    'ws_limits': 'WebSocket rate limits',
    'backoff': 'Retry backoff strategies',
    'concurrency': 'Internal parallel dispatch',
    'outbox': 'Intent outbox queue',
    'intent_sync': 'Cross-worker intent sync',
    'redis_extra': 'SUBPACKAGE: Redis stores (optional)',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

