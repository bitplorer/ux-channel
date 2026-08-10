"""Compatibility shim — implementation: ``ux_channel.ops_dx.cli``.

Stable::

    from ux_channel.cli import ...

Preferred::

    from ux_channel.ops_dx.cli import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.cli import *  # noqa: F403

import ux_channel.ops_dx.cli as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
