"""Application API — curated exports for product code.

This package is the **narrow public surface** for application authors.
It re-exports the same objects as the package root; it is not a second
implementation.

Prefer either::

    from ux_channel import Channel, Region, CapService, state

or, when you want an explicit “API surface only” import path::

    from ux_channel.api import Channel, Region, CapService, state

Power features live under cohesive packages (``host``, ``protocol``,
``paint``, ``asgi``, …) — import those by intent, not from here.
"""
from __future__ import annotations

from ux_channel import (
    ActionError,
    ActionNotFound,
    ActionRegistry,
    CapError,
    CapService,
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
    "CapService",
    "CapError",
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
