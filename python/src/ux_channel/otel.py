"""Compatibility shim — implementation: ``ux_channel.ops_dx.otel``.

Stable::

    from ux_channel.otel import ...

Preferred::

    from ux_channel.ops_dx.otel import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.otel import *  # noqa: F403

import ux_channel.ops_dx.otel as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
