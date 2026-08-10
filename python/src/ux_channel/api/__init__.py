"""Application API — curated exports for product code.

Same objects as the package root; not a second implementation.

::

    from ux_channel.api import Channel, Region, CapService, state

Power features: import from ``host``, ``protocol``, ``render``, ``security``, …
"""
# MANUAL_PUBLIC_API — layout sync must not overwrite
from __future__ import annotations

from ux_channel._version import __version__, __version_info__
from ux_channel.devtools import AuditBundle, attach_audit
from ux_channel.devtools.agents_api import Agents, attach_agents
from ux_channel.devtools.agents_api import agents as _agents
from ux_channel.host import Channel, ChannelConfig, Region, RegionBook, create_channel
from ux_channel.host.context import ActionContext, Principal
from ux_channel.host.state_api import attach_state, state
from ux_channel.protocol import CapError, CapService, Intent, Result, morph, toast

agents = _agents

__all__ = [
    "__version__",
    "__version_info__",
    "Channel",
    "ChannelConfig",
    "Region",
    "RegionBook",
    "CapService",
    "CapError",
    "Intent",
    "Result",
    "morph",
    "toast",
    "state",
    "attach_state",
    "agents",
    "attach_agents",
    "Agents",
    "attach_audit",
    "AuditBundle",
    "ActionContext",
    "Principal",
    "create_channel",
]
