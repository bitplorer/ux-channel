"""Compatibility shim — implementation: ``ux_channel.paint.placement``.

Stable::

    from ux_channel.placement import ...

Preferred::

    from ux_channel.paint.placement import ...
"""
from __future__ import annotations

from ux_channel.paint.placement import *  # noqa: F403

import ux_channel.paint.placement as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
