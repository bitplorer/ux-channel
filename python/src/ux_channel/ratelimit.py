"""Compatibility shim — implementation: ``ux_channel.security_plane.ratelimit``.

Stable::

    from ux_channel.ratelimit import ...

Preferred::

    from ux_channel.security_plane.ratelimit import ...
"""
from __future__ import annotations

from ux_channel.security_plane.ratelimit import *  # noqa: F403

import ux_channel.security_plane.ratelimit as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
