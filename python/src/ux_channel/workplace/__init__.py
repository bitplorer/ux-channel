"""
Workplace — policy-shaped room on a Channel (L4 plane).

Design
    Coordinate multi-party rooms/tickets on the same Channel trust story.
    Does not replace application ``agents(ch)`` / ``state(ch)``.

Architecture
    L4 plane — ticket + mesh + room modules; adapters stay host-owned.

Implementation

One import surface::

    from ux_channel.workplace import (
        workplace, Workplace,
        issue_mesh_membership, workplace_from_membership,
        sign_workplace_ticket, revoke_mesh_membership,
    )

Submodules (advanced)::

    ux_channel.workplace.ticket  — signed membership tickets
    ux_channel.workplace.mesh    — WebRTC + workplace co-issuance
    ux_channel.workplace.room    — Workplace class implementation

Does not replace application ``agents(ch)`` / ``state(ch)``.
Adapters stay host-owned (never drivers in core).
"""
from __future__ import annotations

from ux_channel.workplace.room import (
    Workplace,
    WorkplaceError,
    attach_workplace,
    get_workplace,
    workplace,
)
from ux_channel.workplace.ticket import (
    WORKPLACE_TICKET_SALT,
    WorkplaceTicketError,
    claim_from_rtc_ticket,
    claim_from_workplace_ticket,
    revoke_workplace_ticket,
    sign_workplace_ticket,
    verify_workplace_ticket_payload,
)
from ux_channel.workplace.mesh import (
    MeshMembership,
    claim_from_mesh_rtc,
    issue_mesh_membership,
    revoke_mesh_membership,
    workplace_from_rtc,
)

__all__ = [
    "Workplace",
    "WorkplaceError",
    "workplace",
    "attach_workplace",
    "get_workplace",
    "sign_workplace_ticket",
    "claim_from_workplace_ticket",
    "claim_from_rtc_ticket",
    "WorkplaceTicketError",
    "verify_workplace_ticket_payload",
    "revoke_workplace_ticket",
    "WORKPLACE_TICKET_SALT",
    "MeshMembership",
    "issue_mesh_membership",
    "workplace_from_membership",
    "workplace_from_rtc",
    "claim_from_mesh_rtc",
    "revoke_mesh_membership"]


def workplace_from_membership(
    channel,
    membership: MeshMembership,
    *,
    attach: bool = True,
    prefer: str = "workplace_ticket",
    **kwargs,
) -> Workplace:
    """Bind Workplace from ``issue_mesh_membership``; keeps token for revoke."""
    from ux_channel.workplace.mesh import workplace_from_membership as _impl

    wp = _impl(channel, membership, attach=attach, prefer=prefer, **kwargs)
    if prefer != "rtc":
        wp.membership_ticket = membership.workplace_ticket
    return wp
