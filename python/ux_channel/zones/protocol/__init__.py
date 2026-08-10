"""Zone: **protocol**

Wire IR + codecs + capabilities — **shared law with Rust**. Start here for interop.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``types`` — Intent / Result protocol types
* ``ops`` — Result op builders (morph, toast, …)
* ``errors`` — Channel error types
* ``error_map`` — Error code → HTTP / client kind
* ``capability`` — Cap sign/verify (args_hash law)
* ``encode`` — Lift Python returns into Result
* ``serde`` — JSON dumps/loads helper (prefer wire)
* ``jsonutil`` — JSON depth/breadth safety
* ``wire`` — SUBPACKAGE: JSON/CXB codecs + negotiate
* ``py.typed`` — PEP 561 marker
"""
from __future__ import annotations

ZONE = "protocol"
DESCRIPTION = 'Wire IR + codecs + capabilities — **shared law with Rust**. Start here for interop.'

MEMBERS: dict[str, str] = {
    'types': 'Intent / Result protocol types',
    'ops': 'Result op builders (morph, toast, …)',
    'errors': 'Channel error types',
    'error_map': 'Error code → HTTP / client kind',
    'capability': 'Cap sign/verify (args_hash law)',
    'encode': 'Lift Python returns into Result',
    'serde': 'JSON dumps/loads helper (prefer wire)',
    'jsonutil': 'JSON depth/breadth safety',
    'wire': 'SUBPACKAGE: JSON/CXB codecs + negotiate',
    'py.typed': 'PEP 561 marker',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

