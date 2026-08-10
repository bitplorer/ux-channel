"""ux-channel — Intent → Action → Result(ops) for server-driven UI.

**Install:** ``pip install ux-channel`` · **CLI:** ``uxchannel``

Application
-----------
::

    from ux_channel import Channel, Region, CapService, state, agents, morph
    # same objects: from ux_channel.api import ...

Power packages (import by intent)
---------------------------------
``protocol`` · ``host`` · ``render`` · ``security`` · ``wire`` · ``asgi`` ·
``agent_runtime`` · ``mcp`` · ``devtools`` · ``bridge`` · ``realtime`` · …

See ``MENTAL_MODEL.md`` · ``python/STABILITY.md`` · ``PUBLIC_API_FREEZE.md``.
"""

from __future__ import annotations

from ux_channel._version import __version__, __version_info__

# ── Protocol (wire law) ───────────────────────────────────────────────────
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
from ux_channel.protocol.error_map import (
    ERROR_HTTP_STATUS,
    catalog as error_catalog,
    http_status_for,
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
from ux_channel.host.channel import UiBuilder, sel
from ux_channel.host.context import ActionContext, Principal
from ux_channel.host.flow import FailFlow, Flow, attach_flow
from ux_channel.host.idempotency import MemoryIdempotencyStore
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.host.region_directory import (
    RegionDirectory,
    attach_region_directory,
    path_to_uid,
)
from ux_channel.host.ssr_state import (
    Namespace,
    SessionVar,
    SsrState,
    attach_ssr_state,
    ssr_state,
)
from ux_channel.host.state_api import ChannelState, Client, attach_state, state
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
from ux_channel.host.stores import MemoryStateStore, NullStateStore, StateConflict
from ux_channel.host.testing import ChannelTest

# ── AX / audit ────────────────────────────────────────────────────────────
from ux_channel.devtools import AuditBundle, attach_audit, inspect_channel, inspect_enabled
from ux_channel.devtools.agents_api import Agents, EffectReport, attach_agents
from ux_channel.devtools.agents_api import agents as _agents_facade

agents = _agents_facade

# ── Render helpers (common on controls) ───────────────────────────────────
from ux_channel.render import (
    ControlAttrs,
    SafeHtml,
    action_attrs,
    esc,
    mark_safe,
    user_content,
)
from ux_channel.render.html import attr_escape, form_open, json_attr

# ── Public star-import surface (__all__) ──────────────────────────────────
# Application + stable core only. Other names above remain importable as
# ``from ux_channel import X`` for compatibility but are *power* re-exports
# (prefer ``ux_channel.host`` / ``protocol`` / ``render`` / ``devtools``).

__all__ = [
    "__version__",
    "__version_info__",
    # construction
    "Channel",
    "ChannelConfig",
    "create_channel",
    "Region",
    "RegionBook",
    "ActionRegistry",
    # wire + caps (Rust-parity)
    "Intent",
    "Result",
    "ErrorObject",
    "Op",
    "CapService",
    "CapError",
    "ActionError",
    "ActionNotFound",
    "ChannelError",
    # op builders
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
    # handler context
    "ActionContext",
    "Principal",
    # application façades
    "state",
    "attach_state",
    "agents",
    "attach_agents",
    "Agents",
    "attach_audit",
    "AuditBundle",
    # common control/render
    "ControlAttrs",
    "action_attrs",
    "esc",
    "SafeHtml",
    "mark_safe",
    "user_content",
    # error plane
    "http_status_for",
    "ERROR_HTTP_STATUS",
]
