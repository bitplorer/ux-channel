"""Host package — Channel, regions, actions, state (app runtime).

Preferred::

    from ux_channel.host import Channel, Region, RegionBook, ChannelConfig
    # or day-1:
    from ux_channel.api import Channel, Region
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.host.config import ChannelConfig
from ux_channel.host.dx import Channel
from ux_channel.host.region_component import Region
from ux_channel.host.regions import RegionBook, RegionContext, RegionDef
from ux_channel.host.registry import ActionRegistry

PACKAGE = "host"
__all__ = [
    "PACKAGE",
    "Channel",
    "ChannelConfig",
    "Region",
    "RegionBook",
    "RegionContext",
    "RegionDef",
    "ActionRegistry",
]
