"""Compatibility shim — implementation: ``ux_channel.ops_dx.upgrade_check``.

Stable::

    from ux_channel.upgrade_check import ...

Preferred::

    from ux_channel.ops_dx.upgrade_check import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.upgrade_check import *  # noqa: F403

import ux_channel.ops_dx.upgrade_check as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
