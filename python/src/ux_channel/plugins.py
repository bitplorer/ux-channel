"""Compatibility shim — implementation: ``ux_channel.bridge_meta.plugins``.

Stable::

    from ux_channel.plugins import ...

Preferred::

    from ux_channel.bridge_meta.plugins import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.plugins import *  # noqa: F403

import ux_channel.bridge_meta.plugins as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
