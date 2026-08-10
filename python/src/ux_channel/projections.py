"""Compatibility shim — implementation: ``ux_channel.paint.projections``.

Stable::

    from ux_channel.projections import ...

Preferred::

    from ux_channel.paint.projections import ...
"""
from __future__ import annotations

from ux_channel.paint.projections import *  # noqa: F403

import ux_channel.paint.projections as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
