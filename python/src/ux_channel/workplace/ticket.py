"""Workplace tickets — signed membership for policy-shaped rooms.

* Power public via ``ux_channel.workplace``
  (``sign_workplace_ticket``, ``claim_from_workplace_ticket``, …).
* Separate salt from WebRTC RTC tickets so media doors and workplace
  policy can evolve independently.
* **Does not** import Channel boot paths — core stays free of Workplace.

Ticket payload (v1)::

    {"v": 1, "room":…"""

from __future__ import annotations

import time
from typing import Any, Mapping, Optional, Sequence

from ux_channel.foundations.io_channel import IoChannelError, IoRoomClaim, claim_from_mapping  # noqa: I001

__all__ = [
    "WorkplaceTicketError",
    "sign_workplace_ticket",
    "verify_workplace_ticket_payload",
    "claim_from_workplace_ticket",
    "claim_from_rtc_ticket",
    "WORKPLACE_TICKET_SALT",
    "revoke_workplace_ticket",
]

WORKPLACE_TICKET_SALT = "ux-channel-workplace-v1"


class WorkplaceTicketError(IoChannelError):
    """Invalid or expired workplace membership ticket."""


def _serializer(config: Any):
    from itsdangerous import URLSafeTimedSerializer

    secret = getattr(config, "secret", None) or ""
    if not secret:
        raise WorkplaceTicketError("config.secret required to sign workplace tickets")
    return URLSafeTimedSerializer(str(secret), salt=WORKPLACE_TICKET_SALT)


def _ticket_max_age(config: Any, max_age: Optional[int]) -> int:
    if max_age is not None:
        return int(max_age)
    for attr in ("workplace_ticket_max_age", "webrtc_ticket_max_age"):
        v = getattr(config, attr, None)
        if v is not None:
            return int(v or 300)
    return 300


def sign_workplace_ticket(
    config: Any,
    room: str,
    *,
    sub: str = "",
    scopes: Sequence[str] = (),
    trust: Optional[Mapping[str, str]] = None,
    max_age: Optional[int] = None,
) -> str:
    """
    Mint a short-lived workplace membership ticket.

    Bind ``room`` + ``sub`` (peer) + attenuated ``scopes``. Optional ``trust``
    holds **ids only** (order_id, sku, …) — never Quantity magnitudes.
    """
    ser = _serializer(config)
    age = _ticket_max_age(config, max_age)
    payload = {
        "v": 1,
        "room": str(room).strip() or "default",
        "sub": str(sub or "")[:128],
        "scopes": [str(s) for s in scopes],
        "trust": {str(k): str(v) for k, v in dict(trust or {}).items()},
        "iat": int(time.time()),
        "ttl": int(age),
    }
    return ser.dumps(payload)


def verify_workplace_ticket_payload(
    config: Any,
    ticket: str,
    *,
    room: Optional[str] = None,
    max_age: Optional[int] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Return verified payload dict or raise ``WorkplaceTicketError``."""
    from itsdangerous import BadSignature, SignatureExpired

    # Logout / ban denylist (same store as push tickets)
    try:
        from ux_channel.devtools.ticket_revoke import get_revocation_list

        if get_revocation_list().is_revoked(ticket):
            raise WorkplaceTicketError("workplace ticket revoked")
    except WorkplaceTicketError:
        raise
    except Exception:
        pass

    ser = _serializer(config)
    age = _ticket_max_age(config, max_age)
    try:
        # Allow slightly wider serializer window; enforce payload iat+ttl below.
        data = ser.loads(ticket, max_age=max(age, 86400))
    except SignatureExpired as exc:
        raise WorkplaceTicketError("workplace ticket expired") from exc
    except BadSignature as exc:
        raise WorkplaceTicketError("invalid workplace ticket") from exc
    if not isinstance(data, dict):
        raise WorkplaceTicketError("malformed workplace ticket")
    got_room = str(data.get("room") or "")
    if room is not None and got_room != str(room).strip():
        raise WorkplaceTicketError(
            f"ticket room mismatch: got {got_room!r} want {room!r}"
        )
    # Logical expiry from mint (authoritative)
    iat = data.get("iat")
    ttl = data.get("ttl")
    if iat is not None and ttl is not None:
        tnow = time.time() if now is None else float(now)
        if tnow > float(iat) + float(ttl):
            raise WorkplaceTicketError("workplace ticket expired")
    return data


def claim_from_workplace_ticket(
    config: Any,
    ticket: str,
    *,
    room: Optional[str] = None,
    max_age: Optional[int] = None,
    now: Optional[float] = None,
) -> IoRoomClaim:
    """Verify ticket → ``IoRoomClaim`` (membership ≠ ambient trust)."""
    data = verify_workplace_ticket_payload(
        config, ticket, room=room, max_age=max_age, now=now
    )
    iat = data.get("iat")
    ttl = data.get("ttl")
    expires_at: Optional[float] = None
    if iat is not None and ttl is not None:
        expires_at = float(iat) + float(ttl)
    mapping = {
        "room": data.get("room"),
        "peer_id": data.get("sub") or "anonymous",
        "scopes": data.get("scopes") or (),
        "trust": data.get("trust") or {},
        "expires_at": expires_at,
    }
    return claim_from_mapping(mapping)


def claim_from_rtc_ticket(
    config: Any,
    ticket: str,
    room: str,
    *,
    scopes: Sequence[str],
    peer_id: Optional[str] = None,
    max_age: Optional[int] = None,
) -> IoRoomClaim:
    """
    Bridge: verified **WebRTC** RTC ticket + server-side scope policy → claim.

    RTC tickets carry room/sub only (media door). Scopes always come from
    **your** policy argument — never trust the browser to invent them.
    """
    from ux_channel.realtime.webrtc import verify_rtc_ticket

    ok, detail = verify_rtc_ticket(config, ticket, room, max_age=max_age)
    if not ok:
        raise WorkplaceTicketError(detail or "invalid rtc ticket")
    sub = peer_id if peer_id is not None else (detail or "anonymous")
    age = _ticket_max_age(config, max_age)
    return claim_from_mapping(
        {
            "room": room,
            "peer_id": sub or "anonymous",
            "scopes": list(scopes),
            "expires_at": time.time() + float(age),
        }
    )


def revoke_workplace_ticket(ticket: str, *, ttl_s: float | None = None) -> None:
    """Revoke a workplace membership ticket (logout / ban)."""
    from ux_channel.devtools.ticket_revoke import get_revocation_list

    age = 3600.0 if ttl_s is None else float(ttl_s)
    get_revocation_list().revoke(ticket, ttl_s=age)
