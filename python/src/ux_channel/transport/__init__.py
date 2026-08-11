"""Transport helpers — batch, push, streams, outbox (L3).

Design
    Delivery mechanics around Intent/Result: batching, push channels, outbox,
    concurrency helpers. Not the wire codecs and not the ASGI mount.

Architecture
    L3 adapters — HTTP framework mounting lives in ``ux_channel.asgi``; codecs
    in ``wire``. Transport must not redefine IR shapes.

Implementation
    Preferred::

        from ux_channel.transport import batch, push, outbox
"""
from __future__ import annotations

from . import batch, outbox, push

__all__ = ["batch", "outbox", "push"]
