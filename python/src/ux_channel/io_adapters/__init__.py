"""I/O adapters — lab DUT, lights, scanner hardware helpers (L4).

Design
    Optional workplace/hardware adapters; not part of IR law or host core.

Architecture
    L4 plane used by workplace mesh demos. Keep device drivers out of protocol.

Implementation
    Preferred::

        from ux_channel.io_adapters import lab_dut, lights, scanner
"""
from __future__ import annotations

from . import lab_dut, lights, scanner

__all__ = ["lab_dut", "lights", "scanner"]
