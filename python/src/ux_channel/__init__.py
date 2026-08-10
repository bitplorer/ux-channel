"""ux-channel — Intent → Action → Result(ops) for server-driven UI.

**Install:** ``pip install ux-channel`` · **CLI:** ``uxchannel``

Application
-----------
::

    from ux_channel import Channel, Region, CapService, state, agents, morph
    # same objects: from ux_channel.api import ...

Power packages (import by intent — not re-exported on root)
------------------------------------------------------------
``protocol`` · ``host`` · ``host.stores`` · ``render`` · ``security`` ·
``wire`` · ``asgi`` · ``agent_runtime`` · ``mcp`` · ``devtools`` · …

See ``MENTAL_MODEL.md`` · ``python/STABILITY.md`` · ``PUBLIC_API_FREEZE.md``.
"""

from __future__ import annotations

from typing import Any

from ux_channel._version import __version__, __version_info__

# Protocol (wire law) — no encode/renderers path
from ux_channel.protocol import (
    ActionError,
    ActionNotFound,
    CapError,
    CapService,
    ChannelError,
    ErrorObject,
    Go,
    Intent,
    Navigate,
    Op,
    Result,
    clear_errors,
    focus,
    morph,
    navigate,
    noop,
    push_url,
    reload,
    remove,
    scroll,
    set_attr,
    set_text,
    signal_set,
    swap,
    toast,
)
from ux_channel.protocol.error_map import ERROR_HTTP_STATUS, http_status_for

# Host application runtime
from ux_channel.host import (
    ActionRegistry,
    Channel,
    ChannelConfig,
    Region,
    RegionBook,
    create_channel,
)
from ux_channel.host.context import ActionContext, Principal

# Common control / HTML helpers (light path only)
from ux_channel.render import (
    ControlAttrs,
    SafeHtml,
    action_attrs,
    esc,
    mark_safe,
    user_content,
)

__all__ = [
    "__version__",
    "__version_info__",
    "Channel",
    "ChannelConfig",
    "create_channel",
    "Region",
    "RegionBook",
    "ActionRegistry",
    "Intent",
    "Result",
    "ErrorObject",
    "Op",
    "CapService",
    "CapError",
    "ActionError",
    "ActionNotFound",
    "ChannelError",
    "morph",
    "toast",
    "navigate",
    "push_url",
    "swap",
    "remove",
    "set_attr",
    "set_text",
    "signal_set",
    "clear_errors",
    "focus",
    "scroll",
    "reload",
    "noop",
    "Go",
    "Navigate",
    "ActionContext",
    "Principal",
    "state",
    "attach_state",
    "agents",
    "attach_agents",
    "Agents",
    "attach_audit",
    "AuditBundle",
    "ControlAttrs",
    "action_attrs",
    "esc",
    "SafeHtml",
    "mark_safe",
    "user_content",
    "http_status_for",
    "ERROR_HTTP_STATUS",
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
