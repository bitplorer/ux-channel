"""Mesh membership — WebRTC door + Workplace policy as one issuance.

* Core WebRTC stays a media/signaling door; **scopes always from server policy**
* Does not alter ``Channel.boot`` — opt-in upgrade only

Flow::

    issue_mesh_membership(ch, room, sub=…, scopes=[…])
        → rtc_ticket   (ch.webrtc.sign_ticket)
        → workplace_ticket (sign_workplace_ticket)
        → optional Workplace…"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.foundations.io_channel import IoRoomClaim
from ux_channel.workplace.ticket import (
    WorkplaceTicketError,
    claim_from_rtc_ticket,
    claim_from_workplace_ticket,
    revoke_workplace_ticket,
    sign_workplace_ticket,
)

__all__ = [
    "MeshMembership",
    "issue_mesh_membership",
    "workplace_from_rtc",
    "workplace_from_membership",
    "claim_from_mesh_rtc",
    "revoke_mesh_membership",
]


@dataclass(frozen=True)
class MeshMembership:
    """
    One server-issued join for a policy-shaped room.

    * ``rtc_ticket`` — media / signaling door (room + sub)
    * ``workplace_ticket`` — policy membership (room + sub + scopes)
    * ``scopes`` — server policy (never client-invented)
    """

    room: str
    sub: str
    scopes: tuple[str, ...]
    rtc_ticket: str
    workplace_ticket: str
    max_age: int = 300
    trust: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "room": self.room,
            "sub": self.sub,
            "scopes": list(self.scopes),
            "rtc_ticket": self.rtc_ticket,
            "workplace_ticket": self.workplace_ticket,
            "max_age": self.max_age,
            "trust": dict(self.trust),
        }

    def claim(self, config: Any) -> IoRoomClaim:
        """Verify workplace ticket → claim (preferred)."""
        return claim_from_workplace_ticket(
            config, self.workplace_ticket, room=self.room
        )


def issue_mesh_membership(
    channel: Any,
    room: str,
    *,
    sub: str = "",
    scopes: Sequence[str] = (),
    trust: Optional[Mapping[str, str]] = None,
    max_age: Optional[int] = None,
) -> MeshMembership:
    """
    Mint **both** RTC and workplace tickets for the same room/sub.

    Call this on the **server** when a principal is allowed into a room.
    Hand ``rtc_ticket`` to the browser WebRTC client; keep using
    ``workplace_ticket`` (or ``workplace_from_membership``) for policy.
    """
    cfg = getattr(channel, "config", None)
    if cfg is None:
        raise WorkplaceTicketError("channel has no config")
    sub_s = str(sub or "")[:128]
    room_s = str(room).strip() or "default"
    sc = tuple(str(s) for s in scopes)
    trust_m = {str(k): str(v) for k, v in dict(trust or {}).items()}

    # RTC media door
    webrtc = getattr(channel, "webrtc", None)
    if webrtc is not None and hasattr(webrtc, "sign_ticket"):
        rtc = webrtc.sign_ticket(room_s, sub=sub_s)
    else:
        from ux_channel.realtime.webrtc import sign_rtc_ticket

        rtc = sign_rtc_ticket(cfg, room_s, sub=sub_s)

    age = max_age
    if age is None:
        age = int(getattr(cfg, "workplace_ticket_max_age", None)
                  or getattr(cfg, "webrtc_ticket_max_age", 300)
                  or 300)

    wp_tok = sign_workplace_ticket(
        cfg,
        room_s,
        sub=sub_s,
        scopes=sc,
        trust=trust_m,
        max_age=int(age),
    )
    return MeshMembership(
        room=room_s,
        sub=sub_s,
        scopes=sc,
        rtc_ticket=rtc,
        workplace_ticket=wp_tok,
        max_age=int(age),
        trust=trust_m,
    )


def claim_from_mesh_rtc(
    channel: Any,
    rtc_ticket: str,
    room: str,
    *,
    scopes: Sequence[str],
    peer_id: Optional[str] = None,
    max_age: Optional[int] = None,
) -> IoRoomClaim:
    """RTC ticket + **server** scopes → claim (browser cannot invent scopes)."""
    cfg = getattr(channel, "config", None)
    return claim_from_rtc_ticket(
        cfg, rtc_ticket, room, scopes=scopes, peer_id=peer_id, max_age=max_age
    )


def workplace_from_rtc(
    channel: Any,
    rtc_ticket: str,
    room: str,
    *,
    scopes: Sequence[str],
    peer_id: Optional[str] = None,
    max_age: Optional[int] = None,
    attach: bool = True,
    **workplace_kwargs: Any,
) -> Any:
    """
    Build ``Workplace`` from a verified RTC ticket + server scope policy.

    Prefer ``workplace_from_membership`` when you issued both tickets together.
    """
    from ux_channel.workplace.room import workplace

    claim = claim_from_mesh_rtc(
        channel,
        rtc_ticket,
        room,
        scopes=scopes,
        peer_id=peer_id,
        max_age=max_age,
    )
    return workplace(channel, claim=claim, attach=attach, **workplace_kwargs)


def workplace_from_membership(
    channel: Any,
    membership: MeshMembership,
    *,
    attach: bool = True,
    prefer: str = "workplace_ticket",
    **workplace_kwargs: Any,
) -> Any:
    """
    Bind a Workplace from ``issue_mesh_membership`` output.

    ``prefer``:
      * ``workplace_ticket`` (default) — full policy ticket
      * ``rtc`` — media ticket + membership.scopes as policy
    """
    from ux_channel.workplace.room import workplace

    if prefer == "rtc":
        return workplace_from_rtc(
            channel,
            membership.rtc_ticket,
            membership.room,
            scopes=membership.scopes,
            peer_id=membership.sub,
            max_age=membership.max_age,
            attach=attach,
            **workplace_kwargs,
        )
    return workplace(
        channel,
        ticket_token=membership.workplace_ticket,
        room=membership.room,
        attach=attach,
        **workplace_kwargs,
    )


def revoke_mesh_membership(
    membership: MeshMembership,
    *,
    ttl_s: float | None = None,
    channel: Any = None,
) -> None:
    """
    Revoke both workplace and RTC tickets for a membership (logout / ban).

    RTC revoke uses the shared revocation list; workplace verify checks it too.
    """
    from ux_channel.devtools.ticket_revoke import get_revocation_list
    from ux_channel.workplace.ticket import revoke_workplace_ticket

    age = float(ttl_s) if ttl_s is not None else float(membership.max_age or 3600)
    revoke_workplace_ticket(membership.workplace_ticket, ttl_s=age)
    get_revocation_list().revoke(membership.rtc_ticket, ttl_s=age)
    if channel is not None and hasattr(channel, "revoke_ticket"):
        try:
            channel.revoke_ticket(membership.rtc_ticket, ttl_s=age)
        except Exception:
            pass
