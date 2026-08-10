"""Day-1 public surface — prefer this import style for new application code.

Why this module exists
----------------------
``ux_channel`` is large. Day-1 apps should not browse 180 modules.
Importing from ``ux_channel.day1`` documents intent: *I only need the frozen core*.

Full package root (``from ux_channel import Channel``) remains supported and frozen.
This is an additive clarity layer, not a rename.

See: ``python/LAYOUT.md`` (cohesive packages), ``python/ONTOLOGY.md``.
Implementations live under ``ux_channel.host``, ``ux_channel.protocol``, etc.
"""
from __future__ import annotations

from ux_channel import (
    ActionError,
    ActionNotFound,
    ActionRegistry,
    CapabilityError,
    CapabilityService,
    Channel,
    ChannelConfig,
    ChannelError,
    ControlAttrs,
    Intent,
    Region,
    RegionBook,
    RegionContext,
    Result,
    action_attrs,
    agents,
    attach_audit,
    attach_state,
    morph,
    signal_set,
    state,
    toast,
)

__all__ = [
    "Channel",
    "ChannelConfig",
    "Region",
    "RegionBook",
    "RegionContext",
    "Intent",
    "Result",
    "ActionRegistry",
    "CapabilityService",
    "CapabilityError",
    "ChannelError",
    "ActionError",
    "ActionNotFound",
    "ControlAttrs",
    "action_attrs",
    "state",
    "attach_state",
    "agents",
    "attach_audit",
    "morph",
    "toast",
    "signal_set",
]
