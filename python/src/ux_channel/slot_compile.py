"""Compatibility shim — implementation: ``ux_channel.paint.slot_compile``.

Stable::

    from ux_channel.slot_compile import ...

Preferred::

    from ux_channel.paint.slot_compile import ...
"""
from __future__ import annotations

from ux_channel.paint.slot_compile import *  # noqa: F403

import ux_channel.paint.slot_compile as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
