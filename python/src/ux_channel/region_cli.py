"""Compatibility shim — implementation: ``ux_channel.host.region_cli``.

Stable::

    from ux_channel.region_cli import ...

Preferred::

    from ux_channel.host.region_cli import ...
"""
from __future__ import annotations

from ux_channel.host.region_cli import *  # noqa: F403

import ux_channel.host.region_cli as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
