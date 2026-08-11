"""Host package — Channel, regions, actions, state (L2 app runtime).

Design
    Application control plane: boot Channel, register regions/actions, mint
    controls, dispatch Intents, apply Result ops. You own markup; Channel owns
    trust, registry, and region bookkeeping.

Architecture
    L2 host core sits on L1 protocol (caps/IR). Adapters (asgi/wire) and L4
    planes hang off this package — they must not redefine CapService/Channel.

Implementation
    ``channel``, ``regions`` / ``region_component``, ``registry``, ``state_api``,
    ``stores``. Note: ``state`` is not re-exported here (collides with stores
    module path) — use ``state_api`` or package root.

    Preferred::

        from ux_channel.host import Channel, Region, RegionBook, ChannelConfig
        from ux_channel.host.state_api import state
        from ux_channel.host.stores import MemoryStateStore
"""
from __future__ import annotations

from ux_channel.host.channel import Channel
from ux_channel.host.config import ChannelConfig
from ux_channel.host.factory import create_channel
from ux_channel.host.region_component import Region
from ux_channel.host.regions import RegionBook, RegionContext, RegionDef
from ux_channel.host.registry import ActionRegistry

__all__ = [
    "Channel",
    "ChannelConfig",
    "Region",
    "RegionBook",
    "RegionContext",
    "RegionDef",
    "ActionRegistry",
    "create_channel",
]
