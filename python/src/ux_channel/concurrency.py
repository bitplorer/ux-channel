"""Compatibility shim — implementation: ``ux_channel.transport.concurrency``.

Stable::

    from ux_channel.concurrency import ...

Preferred::

    from ux_channel.transport.concurrency import ...
"""
from __future__ import annotations

from ux_channel.transport.concurrency import *  # noqa: F403

import ux_channel.transport.concurrency as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
