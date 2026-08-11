"""Foundations package — quantity, provenance, io_channel (L3 primitives).

Design
    Shared non-UI primitives used by workplace / agents without depending on
    HTML or ASGI.

Architecture
    L3 — optional adapters and value types; not part of IR law.

Implementation
    Public starter: ``Quantity``. Deeper: ``provenance``, ``io_channel`` modules.
    Preferred::

        from ux_channel.foundations import Quantity
"""
from __future__ import annotations

from ux_channel.foundations.quantity import Quantity

__all__ = ["Quantity"]
