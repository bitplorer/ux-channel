"""Cohesive package: **host**

Channel, Region (one slot), RegionBook (registry), state, day1. App surface.

Modules: actions_file, catalog, config, context, dx, factory, flow, hooks, idempotency, live, nonce, planes, recipes, region_cli, region_component, region_directory, regions, registry, ssr_state, state, state_api, testing

Import: ``from ux_channel.host.MODULE import Symbol``
Public apps: ``from ux_channel.day1 import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['actions_file', 'catalog', 'config', 'context', 'dx', 'factory', 'flow', 'hooks', 'idempotency', 'live', 'nonce', 'planes', 'recipes', 'region_cli', 'region_component', 'region_directory', 'regions', 'registry', 'ssr_state', 'state', 'state_api', 'testing']
PACKAGE = 'host'
__all__ = ["MEMBERS", "PACKAGE"]
