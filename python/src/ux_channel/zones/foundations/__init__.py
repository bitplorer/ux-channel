"""Zone / package: **foundations**

Quantity, provenance, I/O channel.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'foundations'
DESCRIPTION = 'Quantity, provenance, I/O channel.'
MEMBERS = {'io_channel': 'I/O channel — authorize and record I/O intents; never own device buses.', 'provenance': 'Provenance — durable source stamps for sensitive values.', 'quantity': 'Quantity — store-grounded measure (magnitude + unit + provenance).'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
