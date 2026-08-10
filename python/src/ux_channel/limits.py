"""Compatibility shim — implementation: ``ux_channel.security_plane.limits``.

Stable::

    from ux_channel.limits import ...

Preferred::

    from ux_channel.security_plane.limits import ...
"""
from __future__ import annotations

from ux_channel.security_plane.limits import *  # noqa: F403

import ux_channel.security_plane.limits as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
