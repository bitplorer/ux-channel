"""Zone: **foundations**

Quantity, provenance, I/O, workplace — **domain integrity**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``quantity`` — Store-grounded measures
* ``provenance`` — Source stamps for sensitive values
* ``io_channel`` — I/O channel authorize/record
* ``io_adapters`` — SUBPACKAGE: sample I/O adapters
* ``workplace`` — SUBPACKAGE: rooms/mesh/tickets
"""
from __future__ import annotations

ZONE = "foundations"
DESCRIPTION = 'Quantity, provenance, I/O, workplace — **domain integrity**.'

MEMBERS: dict[str, str] = {
    'quantity': 'Store-grounded measures',
    'provenance': 'Source stamps for sensitive values',
    'io_channel': 'I/O channel authorize/record',
    'io_adapters': 'SUBPACKAGE: sample I/O adapters',
    'workplace': 'SUBPACKAGE: rooms/mesh/tickets',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

