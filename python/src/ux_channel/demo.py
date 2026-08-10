"""Compatibility shim — implementation: ``ux_channel.paint.demo``.

Stable::

    from ux_channel.demo import ...

Preferred::

    from ux_channel.paint.demo import ...
"""
from __future__ import annotations

from ux_channel.paint.demo import *  # noqa: F403

import ux_channel.paint.demo as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
