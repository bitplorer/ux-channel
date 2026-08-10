# MANUAL_PUBLIC_API
"""Cohesive package: **io_adapters**

Implementation package.

Modules: lab_dut, lights, scanner

Import: ``from ux_channel.io_adapters.MODULE import Symbol``
Public apps: ``from ux_channel.api import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['lab_dut', 'lights', 'scanner']
PACKAGE = 'io_adapters'
__all__ = ["MEMBERS", "PACKAGE"]
