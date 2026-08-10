"""Compatibility shim — implementation: ``ux_channel.ops_dx.info``.

Stable::

    from ux_channel.info import ...

Preferred::

    from ux_channel.ops_dx.info import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.info import *  # noqa: F403

import ux_channel.ops_dx.info as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
