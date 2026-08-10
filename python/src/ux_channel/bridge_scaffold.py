"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_scaffold``.

Stable::

    from ux_channel.bridge_scaffold import ...

Preferred::

    from ux_channel.bridge_meta.bridge_scaffold import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_scaffold import *  # noqa: F403

import ux_channel.bridge_meta.bridge_scaffold as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
