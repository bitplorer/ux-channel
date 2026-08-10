"""Compatibility shim — implementation: ``ux_channel.protocol.error_map``.

Stable::

    from ux_channel.error_map import ...

Preferred::

    from ux_channel.protocol.error_map import ...
"""
from __future__ import annotations

from ux_channel.protocol.error_map import *  # noqa: F403

import ux_channel.protocol.error_map as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
