"""Compatibility shim — implementation: ``ux_channel.host.regions``.

Stable::

    from ux_channel.regions import ...

Preferred::

    from ux_channel.host.regions import ...
"""
from __future__ import annotations

from ux_channel.host.regions import *  # noqa: F403

import ux_channel.host.regions as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
