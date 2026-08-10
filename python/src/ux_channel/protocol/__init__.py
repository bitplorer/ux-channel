"""Cohesive package: **protocol**

Modules: capability, encode, error_map, errors, jsonutil, ops, serde, types

Import: ``from ux_channel.protocol.MODULE import Symbol``
Legacy: ``from ux_channel.MODULE import Symbol`` (shim at top-level).
"""
from __future__ import annotations

MEMBERS = ['capability', 'encode', 'error_map', 'errors', 'jsonutil', 'ops', 'serde', 'types']
PACKAGE = 'protocol'
__all__ = ["MEMBERS", "PACKAGE"]
