"""Compatibility shim — implementation: ``ux_channel.host.region_directory``.

Stable::

    from ux_channel.region_directory import ...

Preferred::

    from ux_channel.host.region_directory import ...
"""
from __future__ import annotations

from ux_channel.host.region_directory import *  # noqa: F403

import ux_channel.host.region_directory as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
