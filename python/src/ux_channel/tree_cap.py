"""Compatibility shim — implementation: ``ux_channel.security_plane.tree_cap``.

Stable::

    from ux_channel.tree_cap import ...

Preferred::

    from ux_channel.security_plane.tree_cap import ...
"""
from __future__ import annotations

from ux_channel.security_plane.tree_cap import *  # noqa: F403

import ux_channel.security_plane.tree_cap as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
