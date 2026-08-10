"""Navigational zones aligned with cohesive packages.

Physical packages (preferred for new code)::

    from ux_channel.host.dx import Channel
    from ux_channel.protocol.capability import CapabilityService

Legacy shims (still supported)::

    from ux_channel.dx import Channel
"""
from __future__ import annotations

from . import agents as agents
from . import asgi as asgi
from . import bridge_meta as bridge_meta
from . import bridges as bridges
from . import components as components
from . import foundations as foundations
from . import host as host
from . import legacy_shims as legacy_shims
from . import mcp as mcp
from . import ops_dx as ops_dx
from . import paint as paint
from . import protocol as protocol
from . import realtime as realtime
from . import security_plane as security_plane
from . import transport as transport
from . import wire as wire
from . import workplace as workplace

ZONES = {
    "agents": agents,
    "asgi": asgi,
    "bridge_meta": bridge_meta,
    "bridges": bridges,
    "components": components,
    "foundations": foundations,
    "host": host,
    "legacy_shims": legacy_shims,
    "mcp": mcp,
    "ops_dx": ops_dx,
    "paint": paint,
    "protocol": protocol,
    "realtime": realtime,
    "security_plane": security_plane,
    "transport": transport,
    "wire": wire,
    "workplace": workplace,
}

__all__ = ["ZONES", "help_all", *list(ZONES.keys())]

def help_all() -> str:
    return "\n---\n".join(ZONES[k].help() for k in ZONES)
