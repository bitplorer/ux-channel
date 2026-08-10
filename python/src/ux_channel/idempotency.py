"""Compatibility shim — implementation: ``ux_channel.host.idempotency``.

Stable: ``from ux_channel.idempotency import ...``
Preferred package path: ``ux_channel.host.idempotency``
"""
from __future__ import annotations

from ux_channel.host.idempotency import *  # noqa: F403
import ux_channel.host.idempotency as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
