"""Compatibility shim — implementation: ``ux_channel.bridge_meta.guest_runtime``.

Stable::

    from ux_channel.guest_runtime import ...

Preferred::

    from ux_channel.bridge_meta.guest_runtime import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.guest_runtime import *  # noqa: F403

import ux_channel.bridge_meta.guest_runtime as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
