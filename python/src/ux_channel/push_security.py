"""Compatibility shim — implementation: ``ux_channel.security_plane.push_security``.

Stable::

    from ux_channel.push_security import ...

Preferred::

    from ux_channel.security_plane.push_security import ...
"""
from __future__ import annotations

from ux_channel.security_plane.push_security import *  # noqa: F403

import ux_channel.security_plane.push_security as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
