"""Cohesive package: **bridge**

Bridge contracts, scaffold, guest runtime. Presets: bridges/.

Modules: bridge_api, bridge_contract, bridge_plane, bridge_preset_gen, bridge_protocol, bridge_scaffold, bridge_style, guest_runtime, plugins

Import: ``from ux_channel.bridge.MODULE import Symbol``
Public apps: ``from ux_channel.api import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['bridge_api', 'bridge_contract', 'bridge_plane', 'bridge_preset_gen', 'bridge_protocol', 'bridge_scaffold', 'bridge_style', 'guest_runtime', 'plugins']
PACKAGE = 'bridge'
__all__ = ["MEMBERS", "PACKAGE"]
