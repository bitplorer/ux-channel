"""Cohesive package: **host** — Channel, regions, actions, state (day-1 surface).

Naming (important)
------------------
* ``Region`` — **one** morphable DOM slot. Prefer this in application code.
* ``RegionBook`` — registry of all slots on a Channel (``ch.regions``).
  **Not** a rename of ``Region``; both types always existed.
* ``RegionDirectory`` — optional FS/package discovery into the book.

Modules: actions_file, catalog, config, context, day1, dx, factory, flow, hooks, idempotency, live, nonce, planes, recipes, region_cli, region_component, region_directory, regions, registry, ssr_state, state, state_api, testing

Import: ``from ux_channel.host.region_component import Region``
Legacy: ``from ux_channel import Region`` (shim).
"""
from __future__ import annotations

MEMBERS = ['actions_file', 'catalog', 'config', 'context', 'day1', 'dx', 'factory', 'flow', 'hooks', 'idempotency', 'live', 'nonce', 'planes', 'recipes', 'region_cli', 'region_component', 'region_directory', 'regions', 'registry', 'ssr_state', 'state', 'state_api', 'testing']
PACKAGE = "host"
__all__ = ["MEMBERS", "PACKAGE"]
