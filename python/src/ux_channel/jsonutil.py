"""Compatibility shim — implementation: ``ux_channel.protocol.jsonutil``.

Stable::

    from ux_channel.jsonutil import ...

Preferred::

    from ux_channel.protocol.jsonutil import ...
"""
from __future__ import annotations

from ux_channel.protocol.jsonutil import *  # noqa: F403

import ux_channel.protocol.jsonutil as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
