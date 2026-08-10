"""Cohesive package: **transport**

batch, push, ws helpers. ASGI adapters live in asgi/.

Modules: backoff, batch, concurrency, cors, intent_sync, middleware, outbox, push, stream, ws_limits, ws_protocol

Import: ``from ux_channel.transport.MODULE import Symbol``
Public apps: ``from ux_channel.day1 import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['backoff', 'batch', 'concurrency', 'cors', 'intent_sync', 'middleware', 'outbox', 'push', 'stream', 'ws_limits', 'ws_protocol']
PACKAGE = 'transport'
__all__ = ["MEMBERS", "PACKAGE"]
