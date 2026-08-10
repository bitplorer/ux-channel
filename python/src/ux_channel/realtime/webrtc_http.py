"""
HTTP helpers for the WebRTC plane — keep FastAPI routes thin.

Mirrors the style of ``push_security`` / ``ws_security``: pure functions,
explicit status+body dicts, no framework imports.

Security chain (every poll/post)::

    authorize_rtc (origin + ticket)
    → peer id sanitize / min length
    → allow_rtc_traffic (rate)
    → store.poll / store.signal
"""

from __future__ import annotations

from typing import Any, Mapping

from ux_channel.realtime.webrtc import (
    _peer_id_ok,
    _sanitize_id,
    allow_rtc_traffic,
    authorize_rtc,
    get_rtc_store,
)
from ux_channel.realtime.webrtc_metrics import note_auth_fail

__all__ = [
    "handle_rtc_poll",
    "handle_rtc_post",
    "handle_rtc_ice",
    "extract_rtc_ticket",
]


def extract_rtc_ticket(
    *,
    query: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    body: Mapping[str, Any] | None = None,
) -> str | None:
    """Ticket from query, header ``X-Channel-Rtc-Ticket``, or JSON body."""
    if body and body.get("ticket"):
        return str(body["ticket"])
    if query and query.get("ticket"):
        return str(query["ticket"])
    if headers:
        for k, v in headers.items():
            if k.lower() == "x-channel-rtc-ticket" and v:
                return str(v)
    return None


def _gate(
    config: Any,
    *,
    room: str,
    peer: str,
    ticket: str | None,
    origin: str | None,
    host: str | None,
    client_key: str = "",
    cost: float = 1.0,
) -> tuple[int, dict[str, Any]] | None:
    """Shared auth + peer + rate gate. Returns error response or None if OK."""
    ok, reason = authorize_rtc(config, room, ticket=ticket, origin=origin, host=host)
    if not ok:
        note_auth_fail()
        return 403, {"ok": False, "error": reason or "unauthorized"}
    peer_s = _sanitize_id(peer)
    if not peer_s or not _peer_id_ok(peer_s, config):
        return 400, {"ok": False, "error": "invalid peer id"}
    allowed, why = allow_rtc_traffic(
        config,
        peer=peer_s,
        room=room,
        cost=cost,
        client_key=client_key,
    )
    if not allowed:
        return 429, {"ok": False, "error": why or "rate limited"}
    return None


def handle_rtc_poll(
    config: Any,
    *,
    room: str,
    peer: str,
    name: str = "",
    since: int = 0,
    ticket: str | None = None,
    origin: str | None = None,
    host: str | None = None,
    client_key: str = "",
) -> tuple[int, dict[str, Any]]:
    """Authorize + rate-limit + poll. Returns ``(http_status, body_dict)``."""
    err = _gate(
        config,
        room=room,
        peer=peer,
        ticket=ticket,
        origin=origin,
        host=host,
        client_key=client_key,
        cost=1.0,
    )
    if err is not None:
        return err
    store = get_rtc_store(config)
    try:
        out = store.poll(room, peer, name=name, since=since)
        return 200, out
    except OverflowError as exc:
        return 409, {"ok": False, "error": str(exc)}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}


def handle_rtc_post(
    config: Any,
    body: Mapping[str, Any],
    *,
    ticket: str | None = None,
    origin: str | None = None,
    host: str | None = None,
    client_key: str = "",
) -> tuple[int, dict[str, Any]]:
    """Authorize + rate-limit + signal|leave."""
    if not isinstance(body, Mapping):
        return 400, {"ok": False, "error": "object required"}
    room = str(body.get("room") or "default")
    tok = ticket or (str(body.get("ticket")) if body.get("ticket") else None)
    op = str(body.get("op") or "").lower()
    peer = str(body.get("from") or body.get("peer") or "")
    # signal floods cost more than leave
    cost = 2.0 if op == "signal" else 1.0
    err = _gate(
        config,
        room=room,
        peer=peer or "anon",
        ticket=tok,
        origin=origin,
        host=host,
        client_key=client_key,
        cost=cost,
    )
    if err is not None:
        return err

    store = get_rtc_store(config)
    try:
        if op == "leave":
            return 200, store.leave(room, str(body.get("peer") or peer or ""))
        if op == "signal":
            kind = str(body.get("kind") or "")
            out = store.signal(
                room,
                from_peer=str(body.get("from") or ""),
                to_peer=str(body.get("to") or ""),
                kind=kind,
                payload=body.get("payload"),
            )
            return 200, out
        return 400, {"ok": False, "error": "op must be signal|leave"}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    except OverflowError as exc:
        return 409, {"ok": False, "error": str(exc)}


def handle_rtc_ice(
    config: Any,
    *,
    room: str = "default",
    ticket: str | None = None,
    origin: str | None = None,
    host: str | None = None,
    sub: str = "uid",
    ttl_s: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Authenticated ICE list (STUN + short-lived TURN).

    Same gate as poll (origin + ticket). Never for anonymous HTML embeds.
    """
    ok, reason = authorize_rtc(config, room, ticket=ticket, origin=origin, host=host)
    if not ok:
        note_auth_fail()
        return 403, {"ok": False, "error": reason or "unauthorized"}
    # Build via a lightweight plane-less helper
    from ux_channel.realtime.webrtc_turn import ice_servers_with_turn

    stun = [{"urls": "stun:stun.l.google.com:19302"}]
    # honor config.webrtc_ice_servers stun-only entries
    extra = getattr(config, "webrtc_ice_servers", None) if config else None
    if extra:
        stun = [
            {"urls": s["urls"]}
            for s in extra
            if isinstance(s, dict) and s.get("urls") and not s.get("credential")
        ] or stun
    servers = ice_servers_with_turn(
        stun=stun, username=sub or "uid", ttl_s=ttl_s
    )
    return 200, {"ok": True, "iceServers": servers, "room": room}
