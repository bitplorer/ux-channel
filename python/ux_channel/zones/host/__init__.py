"""Zone: **host**

Channel, regions, actions, state — **day-1 application surface**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``day1`` — Narrow day-1 import façade
* ``dx`` — Channel façade (boot, control, done)
* ``config`` — ChannelConfig
* ``registry`` — Action dispatch kernel
* ``context`` — ActionContext / Principal
* ``regions`` — RegionBook + @region
* ``region_component`` — Class-style Region
* ``region_directory`` — Opt-in FS region discovery
* ``region_cli`` — CLI scaffold for regions
* ``flow`` — on / done / fail / refresh verbs
* ``factory`` — Bootstrap helper
* ``hooks`` — Action lifecycle hooks
* ``state`` — Draft / state stores
* ``state_api`` — state(ch) day-1 API
* ``ssr_state`` — Session values for re-paint
* ``planes`` — Client/db safety helpers for state
* ``live`` — In-process topic → region bind
* ``nonce`` — One-shot / nonce store
* ``idempotency`` — Idempotency store
* ``actions_file`` — File-based action discovery
* ``catalog`` — Action catalog metadata
* ``testing`` — ChannelTest helpers
* ``recipes`` — Named day-1 patterns
"""
from __future__ import annotations

ZONE = "host"
DESCRIPTION = 'Channel, regions, actions, state — **day-1 application surface**.'

MEMBERS: dict[str, str] = {
    'day1': 'Narrow day-1 import façade',
    'dx': 'Channel façade (boot, control, done)',
    'config': 'ChannelConfig',
    'registry': 'Action dispatch kernel',
    'context': 'ActionContext / Principal',
    'regions': 'RegionBook + @region',
    'region_component': 'Class-style Region',
    'region_directory': 'Opt-in FS region discovery',
    'region_cli': 'CLI scaffold for regions',
    'flow': 'on / done / fail / refresh verbs',
    'factory': 'Bootstrap helper',
    'hooks': 'Action lifecycle hooks',
    'state': 'Draft / state stores',
    'state_api': 'state(ch) day-1 API',
    'ssr_state': 'Session values for re-paint',
    'planes': 'Client/db safety helpers for state',
    'live': 'In-process topic → region bind',
    'nonce': 'One-shot / nonce store',
    'idempotency': 'Idempotency store',
    'actions_file': 'File-based action discovery',
    'catalog': 'Action catalog metadata',
    'testing': 'ChannelTest helpers',
    'recipes': 'Named day-1 patterns',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

