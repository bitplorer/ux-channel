"""Compatibility shim — implementation: ``ux_channel.transport.intent_sync``.

Stable::

    from ux_channel.intent_sync import ...

Preferred::

    from ux_channel.transport.intent_sync import ...
"""
from __future__ import annotations

from ux_channel.transport.intent_sync import *  # noqa: F403

import ux_channel.transport.intent_sync as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
