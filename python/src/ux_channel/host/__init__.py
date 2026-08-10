"""Host package — Channel, regions, actions, state (app runtime).

Preferred::

    from ux_channel.host import Channel, Region, RegionBook, ChannelConfig
    from ux_channel.host.state_api import state   # note: not host.state (module)

``state`` cannot be re-exported on this package root — it collides with
the ``host.state`` module (stores). Use ``state_api`` or package root
``from ux_channel import state``.
"""
from __future__ import annotations

from ux_channel.host.channel import Channel
from ux_channel.host.config import ChannelConfig
from ux_channel.host.factory import create_channel
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
    "create_channel",
]
