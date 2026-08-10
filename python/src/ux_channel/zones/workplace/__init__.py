"""Zone / package: **workplace**

SUBPACKAGE: rooms/mesh/tickets.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'workplace'
DESCRIPTION = 'SUBPACKAGE: rooms/mesh/tickets.'
MEMBERS = {'mesh': 'Mesh membership — WebRTC door + Workplace policy as one issuance.', 'room': 'Workplace room façade — claim · gate · AX · I/O (package-private module).', 'ticket': 'Workplace tickets — signed membership for policy-shaped rooms.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
