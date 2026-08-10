"""Zone / package: **transport**

Batch, push, WS helpers (ASGI subpackage stays separate).

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'transport'
DESCRIPTION = 'Batch, push, WS helpers (ASGI subpackage stays separate).'
MEMBERS = {'backoff': 'Backoff strategies for retries (batch, clients, workers).', 'batch': 'Batch dispatch — multiple Intents, one HTTP round-trip.', 'concurrency': 'Internal parallel + concurrent dispatch for **ux-channel**.', 'cors': 'CORS helper for browser apps that call Channel from a separate frontend origin.', 'intent_sync': 'Real-time intent sync across workers (Redis pub/sub).', 'middleware': 'ASGI middleware helpers for production DX (request IDs, optional client version)', 'outbox': 'Intent outbox — queue Intents when the channel/mesh cannot apply them yet.', 'push': 'Server push bus — server-initiated Results.', 'stream': 'SSE streaming of Result chunks — progressive apply for long actions.', 'ws_limits': 'WebSocket connection / message rate limits (Wave 1).', 'ws_protocol': 'WebSocket message helpers for uxchannel duplex channel.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
