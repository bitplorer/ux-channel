"""Compatibility shim — implementation: ``ux_channel.realtime.media``.

Stable::

    from ux_channel.media import ...

Preferred::

    from ux_channel.realtime.media import ...
"""
from __future__ import annotations

from ux_channel.realtime.media import *  # noqa: F403

import ux_channel.realtime.media as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
