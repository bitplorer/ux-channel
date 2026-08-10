"""Compatibility shim — implementation: ``ux_channel.protocol.encode``.

Stable::

    from ux_channel.encode import ...

Preferred::

    from ux_channel.protocol.encode import ...
"""
from __future__ import annotations

from ux_channel.protocol.encode import *  # noqa: F403

import ux_channel.protocol.encode as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
