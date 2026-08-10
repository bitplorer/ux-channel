"""Compatibility shim — implementation: ``ux_channel.security_plane.security_events``.

Stable::

    from ux_channel.security_events import ...

Preferred::

    from ux_channel.security_plane.security_events import ...
"""
from __future__ import annotations

from ux_channel.security_plane.security_events import *  # noqa: F403

import ux_channel.security_plane.security_events as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
