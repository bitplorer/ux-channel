"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_plane``.

Stable::

    from ux_channel.bridge_plane import ...

Preferred::

    from ux_channel.bridge_meta.bridge_plane import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_plane import *  # noqa: F403

import ux_channel.bridge_meta.bridge_plane as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
