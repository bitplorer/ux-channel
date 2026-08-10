"""Cohesive package: **protocol**

Wire IR + CapService (Rust-parity mint/verify). Shared law with rust/.

Modules: capability, encode, error_map, errors, jsonutil, ops, serde, types

Import: ``from ux_channel.protocol.MODULE import Symbol``
Public apps: ``from ux_channel.day1 import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['capability', 'encode', 'error_map', 'errors', 'jsonutil', 'ops', 'serde', 'types']
PACKAGE = 'protocol'
__all__ = ["MEMBERS", "PACKAGE"]
