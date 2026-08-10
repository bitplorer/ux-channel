"""Cohesive package: **foundations**

Quantity, provenance, io_channel.

Modules: io_channel, provenance, quantity

Import: ``from ux_channel.foundations.MODULE import Symbol``
Public apps: ``from ux_channel.day1 import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['io_channel', 'provenance', 'quantity']
PACKAGE = 'foundations'
__all__ = ["MEMBERS", "PACKAGE"]
