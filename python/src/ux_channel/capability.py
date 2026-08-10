"""Compatibility shim — implementation: ``ux_channel.protocol.capability``.

Stable::

    from ux_channel.capability import ...

Preferred::

    from ux_channel.protocol.capability import ...
"""
from __future__ import annotations

from ux_channel.protocol.capability import *  # noqa: F403

import ux_channel.protocol.capability as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
