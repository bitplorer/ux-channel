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

from ux_channel._version import __version__, __version_info__

# Protocol (wire law)
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
from ux_channel.host.state_api import attach_state, state

# AX / audit façades
from ux_channel.devtools import AuditBundle, attach_audit
from ux_channel.devtools.agents_api import Agents, attach_agents
from ux_channel.devtools.agents_api import agents as _agents_facade

agents = _agents_facade

# Common control / HTML helpers
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
