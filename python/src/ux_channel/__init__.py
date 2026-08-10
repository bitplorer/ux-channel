"""ux-channel 0.1.0 — Intent → Action → Result(ops) for server-driven UI.

Brand lines
-----------
| Layer | Name |
|-------|------|
| **PyPI / pip** | ``ux-channel`` |
| **Import** | ``ux_channel`` |
| **CLI** | ``uxchannel`` |

Day-1
-----
``Channel.boot`` → ``@region`` / ``@on`` → ``control`` → ``agents`` / ``state`` → ``done``.

Prefer ``from ux_channel.host.day1 import Channel, Region, …`` for new apps
(same objects as root; narrower speech). See ``python/ONTOLOGY.md`` + ``STRUCTURE.md``.

Import map (stable)
-------------------
::

    # Day-1
    from ux_channel import Channel, ChannelConfig, agents, state, attach_audit

    # Power — import by concern (not on root)
    from ux_channel.foundations.quantity import Quantity
    from ux_channel.foundations.io_channel import IoGate, IoRoomClaim
    from ux_channel.workplace import workplace, issue_mesh_membership
    from ux_channel.transport.outbox import attach_outbox, drain_outbox
    from ux_channel.security.host_csrf import intent_headers

HTML hosts (or templates) own **markup**. Channel owns **control**, **trust**,
**regions**, and **ops**. See docs/start/API_SURFACE.md · docs/start/LAYERS.md · docs/start/FREEZE_0.1.md.
"""

from __future__ import annotations

from ux_channel._version import __version__, __version_info__

# ── Protocol ──────────────────────────────────────────────────────────────
from ux_channel.protocol.types import ErrorObject, Intent, Result
from ux_channel.protocol.errors import ActionError, ActionNotFound, ChannelError
from ux_channel.protocol.ops import (
    Op,
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
from ux_channel.protocol.encode import Go, Navigate

# ── Runtime ───────────────────────────────────────────────────────────────
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.capability import CapError, CapService
from ux_channel.host.context import ActionContext, Principal
from ux_channel.host.config import ChannelConfig
from ux_channel.host.state import MemoryStateStore, NullStateStore, StateConflict
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.host.idempotency import MemoryIdempotencyStore

# ── Façade + regions ──────────────────────────────────────────────────────
from ux_channel.host.dx import Channel, UiBuilder, sel
from ux_channel.host.regions import RegionBook, RegionContext, RegionDef
from ux_channel.host.region_component import Region
from ux_channel.host.flow import Flow, FailFlow, attach_flow
from ux_channel.host.ssr_state import ssr_state, attach_ssr_state, SsrState, SessionVar, Namespace
from ux_channel.host.planes import (
    planes,
    attach_planes,
    Planes,
    ClientPlane,
    Db,
    ClientSafetyError,
    path_is_risky,
    RISKY_SEGMENTS,
)
from ux_channel.host.state_api import state, attach_state, ChannelState, Client
from ux_channel.ops_dx.agents_api import agents as _agents_facade, attach_agents, Agents, EffectReport

agents = _agents_facade

from ux_channel.host.region_directory import RegionDirectory, path_to_uid, attach_region_directory
from ux_channel.ops_dx.inspect_api import inspect_channel, inspect_enabled
from ux_channel.ops_dx.audit import attach_audit, AuditBundle

# ── HTML safety + control attrs ───────────────────────────────────────────
from ux_channel.paint.html import (
    ControlAttrs,
    action_attrs,
    attr_escape,
    form_open,
    json_attr,
)
from ux_channel.paint.html_safe import SafeHtml, esc, mark_safe, user_content

# ── Error plane ───────────────────────────────────────────────────────────
from ux_channel.protocol.error_map import (
    ERROR_HTTP_STATUS,
    catalog as error_catalog,
    http_status_for,
)

# ── Factory / testing ─────────────────────────────────────────────────────
from ux_channel.host.factory import create_channel
from ux_channel.host.testing import ChannelTest

# Power layers stay off root — import by concern (quantity, workplace, outbox, …)

__all__ = [
    "__version__",
    "__version_info__",
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
    "ActionRegistry",
    "CapError",
    "CapService",
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
