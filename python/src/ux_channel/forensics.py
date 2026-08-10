"""Compatibility shim — implementation: ``ux_channel.ops_dx.forensics``.

Stable::

    from ux_channel.forensics import ...

Preferred::

    from ux_channel.ops_dx.forensics import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.forensics import *  # noqa: F403

import ux_channel.ops_dx.forensics as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
