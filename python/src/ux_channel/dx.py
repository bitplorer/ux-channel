"""Compatibility shim — implementation: ``ux_channel.host.dx``.

Stable::

    from ux_channel.dx import ...

Preferred::

    from ux_channel.host.dx import ...
"""
from __future__ import annotations

from ux_channel.host.dx import *  # noqa: F403

import ux_channel.host.dx as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
