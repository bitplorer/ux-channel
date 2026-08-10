"""Compatibility shim — implementation: ``ux_channel.transport.stream``.

Stable::

    from ux_channel.stream import ...

Preferred::

    from ux_channel.transport.stream import ...
"""
from __future__ import annotations

from ux_channel.transport.stream import *  # noqa: F403

import ux_channel.transport.stream as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
