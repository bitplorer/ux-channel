"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_protocol``.

Stable::

    from ux_channel.bridge_protocol import ...

Preferred::

    from ux_channel.bridge_meta.bridge_protocol import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_protocol import *  # noqa: F403

import ux_channel.bridge_meta.bridge_protocol as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
