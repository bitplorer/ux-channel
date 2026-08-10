"""
Reference I/O adapters — **stubs**, not production drivers.

=================================================================
PUBLIC / PRIVATE
=================================================================
* **Power examples:** scanner, lights, lab DUT patterns.
* Real hardware/OS codecs stay in your app or optional packages.
* All implement ``IoAdapter`` and go through ``IoGate`` / ``run_checked``.

See docs/IO_CHANNEL.md.
"""

from __future__ import annotations

from ux_channel.io_adapters.lab_dut import LabDutAdapter
from ux_channel.io_adapters.lights import LightsAdapter
from ux_channel.io_adapters.scanner import ScannerAdapter

__all__ = ["ScannerAdapter", "LightsAdapter", "LabDutAdapter"]
