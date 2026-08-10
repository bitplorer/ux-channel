"""Compatibility shim — implementation: ``ux_channel.realtime.whip``.

Stable::

    from ux_channel.whip import ...

Preferred::

    from ux_channel.realtime.whip import ...
"""
from __future__ import annotations

from ux_channel.realtime.whip import *  # noqa: F403

import ux_channel.realtime.whip as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
