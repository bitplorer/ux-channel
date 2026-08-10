"""Cohesive package: **protocol**

Wire IR + CapService (Rust-parity mint/verify). Shared law with rust/.

Modules: capability, encode, error_map, errors, jsonutil, ops, serde, types

Import: ``from ux_channel.protocol.MODULE import Symbol``
Legacy: ``from ux_channel.MODULE import Symbol`` (generated alias).

Source of truth: PACKAGE_MAP.json · sync: scripts/sync_python_layout.py
"""
from __future__ import annotations

MEMBERS = ['capability', 'encode', 'error_map', 'errors', 'jsonutil', 'ops', 'serde', 'types']
PACKAGE = 'protocol'
__all__ = ["MEMBERS", "PACKAGE"]
