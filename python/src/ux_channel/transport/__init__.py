"""Cohesive package: **transport**

batch, push, ws helpers. ASGI adapters live in asgi/.

Modules: backoff, batch, concurrency, cors, intent_sync, middleware, outbox, push, stream, ws_limits, ws_protocol

Import: ``from ux_channel.transport.MODULE import Symbol``
Legacy: ``from ux_channel.MODULE import Symbol`` (generated alias).

Source of truth: PACKAGE_MAP.json · sync: scripts/sync_python_layout.py
"""
from __future__ import annotations

MEMBERS = ['backoff', 'batch', 'concurrency', 'cors', 'intent_sync', 'middleware', 'outbox', 'push', 'stream', 'ws_limits', 'ws_protocol']
PACKAGE = 'transport'
__all__ = ["MEMBERS", "PACKAGE"]
