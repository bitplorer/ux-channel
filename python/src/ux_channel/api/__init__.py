"""Application API — curated exports for product code (L2 surface).

Design
    Same objects as the package root application surface — **not** a second
    implementation. Identity law: ``api.Channel is host.Channel is root.Channel``.

Architecture
    Preferred import door for apps. Power features stay in packages
    (``host``, ``protocol``, ``render``, ``security``, …).

Implementation
    Preferred::

        from ux_channel.api import Channel, Region, CapService, state, agents, morph
"""
from __future__ import annotations

from typing import Any

from ux_channel._version import __version__, __version_info__
from ux_channel.host import Channel, ChannelConfig, Region, RegionBook, create_channel
from ux_channel.host.context import ActionContext, Principal
from ux_channel.protocol import (
    CapError,
    CapService,
    Intent,
    Result,
    morph,
    toast,
    navigate,
)

__all__ = [
    "__version__",
    "__version_info__",
    "Channel",
    "ChannelConfig",
    "Region",
    "RegionBook",
    "create_channel",
    "CapService",
    "CapError",
    "Intent",
    "Result",
    "morph",
    "toast",
    "navigate",
    "state",
    "attach_state",
    "agents",
    "attach_agents",
    "Agents",
    "attach_audit",
    "AuditBundle",
    "ActionContext",
    "Principal",
]

_LAZY: dict[str, tuple[str, str]] = {
    "state": ("ux_channel.host.state_api", "state"),
    "attach_state": ("ux_channel.host.state_api", "attach_state"),
    "agents": ("ux_channel.devtools.agents_api", "agents"),
    "attach_agents": ("ux_channel.devtools.agents_api", "attach_agents"),
    "Agents": ("ux_channel.devtools.agents_api", "Agents"),
    "attach_audit": ("ux_channel.devtools.audit", "attach_audit"),
    "AuditBundle": ("ux_channel.devtools.audit", "AuditBundle"),
}


def __getattr__(name: str) -> Any:
    spec = _LAZY.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    mod_name, attr = spec
    val = getattr(importlib.import_module(mod_name), attr)
    globals()[name] = val
    return val
