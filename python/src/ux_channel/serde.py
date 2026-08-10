"""Compatibility shim — implementation: ``ux_channel.protocol.serde``.

Stable::

    from ux_channel.serde import ...

Preferred::

    from ux_channel.protocol.serde import ...
"""
from __future__ import annotations

from ux_channel.protocol.serde import *  # noqa: F403

import ux_channel.protocol.serde as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
