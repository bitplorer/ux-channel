"""Navigational zones for the ux_channel package.

Flat modules stay for **import stability**. Zones make **intent** legible.

See ``python/LAYOUT.md`` and ``python/ONTOLOGY.md``.

Usage::

    from ux_channel.zones import host, protocol
    print(host.help())

    from ux_channel.day1 import Channel, Region
"""
from __future__ import annotations

from . import (
    agents_ax,
    bridges_ui,
    foundations,
    host,
    ops_dx,
    protocol,
    realtime_media,
    render,
    security,
    transport,
)

ZONES = {
    "protocol": protocol,
    "host": host,
    "render": render,
    "security": security,
    "agents_ax": agents_ax,
    "transport": transport,
    "bridges_ui": bridges_ui,
    "foundations": foundations,
    "realtime_media": realtime_media,
    "ops_dx": ops_dx,
}

__all__ = ["ZONES", "help_all", "protocol", "host", "render", "security",
           "agents_ax", "transport", "bridges_ui", "foundations",
           "realtime_media", "ops_dx"]


def help_all() -> str:
    """Human summary of every zone."""
    return "\n---\n".join(ZONES[k].help() for k in ZONES)
