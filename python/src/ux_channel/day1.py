"""Compatibility shim — implementation: ``ux_channel.host.day1``.

Stable::

    from ux_channel.day1 import ...

Preferred::

    from ux_channel.host.day1 import ...
"""
from __future__ import annotations

from ux_channel.host.day1 import *  # noqa: F403

import ux_channel.host.day1 as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
