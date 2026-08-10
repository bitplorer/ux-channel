"""ux-channel — Intent → Action → Result(ops) for server-driven UI.

**Install:** ``pip install ux-channel`` · **Import:** ``ux_channel`` · **CLI:** ``uxchannel``

Application surface
-------------------
::

    from ux_channel import Channel, Region, CapService, state
    # or: from ux_channel.api import Channel, Region, CapService, state

    ch = Channel.boot(...)

Power packages (import by intent)
---------------------------------
``protocol`` · ``host`` · ``render`` · ``security`` · ``transport`` ·
``foundations`` · ``realtime`` · ``bridge`` · ``bridges`` · ``asgi`` ·
``devtools`` · ``wire`` · ``components`` · ``agents`` · ``mcp`` · ``workplace``

Layout: ``python/STABILITY.md`` · Naming: root ``NAMING.md``.
"""

from __future__ import annotations

from ux_channel._version import __version__, __version_info__

# ── Protocol (package surface + encode) ───────────────────────────────────
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

# ── Host runtime ──────────────────────────────────────────────────────────
from ux_channel.host import (
    ActionRegistry,
    Channel,
    ChannelConfig,
    Region,
    RegionBook,
    RegionContext,
    RegionDef,
    create_channel,
)
from ux_channel.host.state_api import ChannelState, Client, attach_state, state
from ux_channel.host.channel import UiBuilder, sel
from ux_channel.host.context import ActionContext, Principal
from ux_channel.host.flow import FailFlow, Flow, attach_flow
from ux_channel.host.idempotency import MemoryIdempotencyStore
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.host.region_directory import RegionDirectory, attach_region_directory, path_to_uid
from ux_channel.host.ssr_state import Namespace, SessionVar, SsrState, attach_ssr_state, ssr_state
from ux_channel.host.stores import MemoryStateStore, NullStateStore, StateConflict
from ux_channel.host.state_planes import (
    RISKY_SEGMENTS,
    ClientPlane,
    ClientSafetyError,
    Db,
    Planes,
    attach_planes,
    path_is_risky,
    planes,
)
from ux_channel.host.testing import ChannelTest

# ── Devtools / agents ─────────────────────────────────────────────────────
from ux_channel.devtools import AuditBundle, attach_audit, inspect_channel, inspect_enabled
from ux_channel.devtools.agents_api import Agents, EffectReport, attach_agents
from ux_channel.devtools.agents_api import agents as _agents_facade

agents = _agents_facade

# ── Render ────────────────────────────────────────────────────────────────
from ux_channel.render import (
    ControlAttrs,
    SafeHtml,
    action_attrs,
    esc,
    mark_safe,
    user_content,
)
from ux_channel.render.html import attr_escape, form_open, json_attr

# ── Error plane ───────────────────────────────────────────────────────────
from ux_channel.protocol.error_map import (
    ERROR_HTTP_STATUS,
    catalog as error_catalog,
    http_status_for,
)

__all__ = [
    "__version__",
    "__version_info__",
    # protocol
    "ErrorObject",
    "Intent",
    "Result",
    "ActionError",
    "ActionNotFound",
    "ChannelError",
    "Op",
    "clear_errors",
    "focus",
    "morph",
    "navigate",
    "noop",
    "push_url",
    "reload",
    "remove",
    "scroll",
    "set_attr",
    "set_text",
    "signal_set",
    "swap",
    "toast",
    "Go",
    "Navigate",
    "CapError",
    "CapService",
    # host
    "ActionRegistry",
    "ActionContext",
    "Principal",
    "ChannelConfig",
    "MemoryStateStore",
    "NullStateStore",
    "StateConflict",
    "MemoryNonceStore",
    "MemoryIdempotencyStore",
    "Channel",
    "UiBuilder",
    "sel",
    "RegionBook",
    "RegionContext",
    "RegionDef",
    "Region",
    "Flow",
    "FailFlow",
    "attach_flow",
    "ssr_state",
    "attach_ssr_state",
    "SsrState",
    "SessionVar",
    "Namespace",
    "planes",
    "attach_planes",
    "Planes",
    "ClientPlane",
    "Db",
    "ClientSafetyError",
    "path_is_risky",
    "RISKY_SEGMENTS",
    "state",
    "attach_state",
    "ChannelState",
    "Client",
    "agents",
    "attach_agents",
    "Agents",
    "EffectReport",
    "RegionDirectory",
    "path_to_uid",
    "attach_region_directory",
    "inspect_channel",
    "inspect_enabled",
    "attach_audit",
    "AuditBundle",
    "ControlAttrs",
    "action_attrs",
    "attr_escape",
    "form_open",
    "json_attr",
    "SafeHtml",
    "esc",
    "mark_safe",
    "user_content",
    "ERROR_HTTP_STATUS",
    "error_catalog",
    "http_status_for",
    "create_channel",
    "ChannelTest",
]
