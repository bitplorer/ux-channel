"""Compatibility shim — implementation: ``ux_channel.ops_dx.observability``.

Stable::

    from ux_channel.observability import ...

Preferred::

    from ux_channel.ops_dx.observability import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.observability import *  # noqa: F403

import ux_channel.ops_dx.observability as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
