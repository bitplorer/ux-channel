"""Zone: **bridges_ui**

npm islands + optional components — **not regions**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``bridge_api`` — Bridge API entry
* ``bridge_plane`` — Bridge plane data+ops
* ``bridge_contract`` — Bridge contracts
* ``bridge_protocol`` — Sealed bridge protocols
* ``bridge_scaffold`` — Scaffold npm bridges
* ``bridge_preset_gen`` — Generate bridge presets
* ``bridge_style`` — Bridge host chrome CSS
* ``bridges`` — SUBPACKAGE: Chart/Leaflet/… presets
* ``components`` — SUBPACKAGE: optional ChannelComponent kit
* ``guest_runtime`` — Sealed guest islands
* ``plugins`` — Plugin hub
"""
from __future__ import annotations

ZONE = "bridges_ui"
DESCRIPTION = 'npm islands + optional components — **not regions**.'

MEMBERS: dict[str, str] = {
    'bridge_api': 'Bridge API entry',
    'bridge_plane': 'Bridge plane data+ops',
    'bridge_contract': 'Bridge contracts',
    'bridge_protocol': 'Sealed bridge protocols',
    'bridge_scaffold': 'Scaffold npm bridges',
    'bridge_preset_gen': 'Generate bridge presets',
    'bridge_style': 'Bridge host chrome CSS',
    'bridges': 'SUBPACKAGE: Chart/Leaflet/… presets',
    'components': 'SUBPACKAGE: optional ChannelComponent kit',
    'guest_runtime': 'Sealed guest islands',
    'plugins': 'Plugin hub',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

