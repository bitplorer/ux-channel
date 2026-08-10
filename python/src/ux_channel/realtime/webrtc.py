"""WebRTC peer-to-peer **signaling** plane for ux-channel.
Boundary
* **This module + HTTP/WS**: roster + JSEP ferry (offer/answer/ICE)
* **Browser only**: media, DTLS-SRTP, SCTP data channels
* **Host only**: call UI markup (use ``ch.webrtc.plugin()`` placement bag)
Wire contract (keep in sync with ``static/ux-webrtc.js``)
Kinds::
    offer | answer | ice | ice-done
Payload shapes (validated by…"""
from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol
from urllib.parse import quote

DEFAULT_ROOM = "default"
MAX_PAYLOAD_BYTES = 32_768
SIGNAL_KINDS = frozenset({"offer", "answer", "ice", "ice-done"})

def validate_signal_payload(kind: str, payload: Any) -> Any:
    """
    Lightweight JSEP-shaped checks (not a full SDP parser).

    Aligns with browser ``RTCSessionDescriptionInit`` / ``RTCIceCandidateInit``
    JSON forms used on the wire. Rejects obvious garbage early so the store
    is not a free-form dump.

    * offer/answer → object with ``type`` matching kind and string ``sdp``
    * ice → object (candidate optional string; null candidate allowed)
    * ice-done → null / omitted only
    """
    kind = (kind or "").lower().strip()
    if kind not in SIGNAL_KINDS:
        raise ValueError(f"kind must be one of {sorted(SIGNAL_KINDS)}")
    if kind == "ice-done":
        if payload is not None and payload != "" and payload != {}:
            # allow explicit null-like
            if payload is not False and payload != 0:
                raise ValueError("ice-done payload must be null")
        return None
    if kind in ("offer", "answer"):
        if not isinstance(payload, dict):
            raise ValueError(f"{kind} payload must be an object (JSEP RTCSessionDescriptionInit)")
        ptype = str(payload.get("type") or "").lower()
        if ptype and ptype != kind:
            raise ValueError(f"{kind} payload.type must be {kind!r} (got {ptype!r})")
        sdp = payload.get("sdp")
        if sdp is None or not isinstance(sdp, str):
            raise ValueError(f"{kind} payload requires string sdp")
        # SDP minimum (RFC 8866 session description starts with v=)
        if sdp.strip() and "v=" not in sdp:
            raise ValueError(f"{kind} sdp does not look like SDP (missing v=)")
        out = dict(payload)
        out["type"] = kind
        out["sdp"] = sdp
        return out
    if kind == "ice":
        if payload is None:
            return None  # some stacks send empty trickle end as ice+null; prefer ice-done
        if not isinstance(payload, dict):
            raise ValueError("ice payload must be an object (RTCIceCandidateInit)")
        # candidate may be null (end-of-candidates in some APIs) — prefer ice-done
        cand = payload.get("candidate", "")
        if cand is not None and not isinstance(cand, str):
            raise ValueError("ice.candidate must be a string or null")
        return dict(payload)
    raise ValueError(f"unknown kind {kind!r}")


def _now() -> float:
    return time.time()


def _sanitize_id(value: str | None) -> str:
    """Allow only [A-Za-z0-9._-] up to 64 chars (room / peer routing ids).

    Path separators are dropped (never stored). Consecutive dots (``..``) are
    collapsed away so ids cannot look like relative paths.
    """
    if not value:
        return ""
    s = str(value).strip()
    out = []
    for ch in s[:64]:
        if ch.isalnum() or ch in "-_.":
            out.append(ch)
    cleaned = "".join(out)
    # neutralize traversal-like sequences
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    cleaned = cleaned.strip(".")
    return cleaned


def _peer_id_ok(peer_id: str, config: Any = None) -> bool:
    """Reject empty / too-short peer ids (set config.webrtc_min_peer_len)."""
    if not peer_id:
        return False
    min_len = 1
    if config is not None:
        min_len = int(getattr(config, "webrtc_min_peer_len", 1) or 0)
    if min_len <= 0:
        return True
    return len(peer_id) >= min_len


def _json_size(payload: Any) -> int:
    try:
        return len(_serde.dumps(payload, default=str).encode("utf-8"))
    except Exception:
        return MAX_PAYLOAD_BYTES + 1


def new_peer_id() -> str:
    return secrets.token_urlsafe(12)


@dataclass
class PeerRecord:
    peer_id: str
    name: str = ""
    last_seen: float = field(default_factory=_now)


@dataclass
class SignalRecord:
    id: int
    room: str
    to_peer: str
    from_peer: str
    kind: str
    payload: Any
    created_at: float = field(default_factory=_now)


class RtcStore(Protocol):
    def poll(
        self,
        room: str,
        peer_id: str,
        *,
        name: str = "",
        since: int = 0,
    ) -> dict[str, Any]: ...

    def signal(
        self,
        room: str,
        *,
        from_peer: str,
        to_peer: str,
        kind: str,
        payload: Any,
    ) -> dict[str, Any]: ...

    def leave(self, room: str, peer_id: str) -> dict[str, Any]: ...

    def subscribe(self, room: str, peer_id: str, q: Any) -> None: ...

    def unsubscribe(self, room: str, peer_id: str, q: Any) -> None: ...


class MemoryRtcStore:
    """
    Process-local WebRTC signaling store (default).

    Also fans out signals to in-process WebSocket subscriber queues so
    trickle ICE does not wait on the next HTTP poll.
    """

    def __init__(
        self,
        *,
        peer_ttl_s: float = 30.0,
        signal_ttl_s: float = 60.0,
        max_peers: int = 8,
    ) -> None:
        self.peer_ttl_s = peer_ttl_s
        self.signal_ttl_s = signal_ttl_s
        self.max_peers = max_peers
        self._lock = threading.RLock()
        self._peers: dict[str, dict[str, PeerRecord]] = {}
        self._signals: list[SignalRecord] = []
        self._seq = 0
        # room -> peer_id -> list of queue.Queue (WS waiters)
        self._subs: dict[str, dict[str, list[Any]]] = {}

    def _gc(self) -> None:
        now = _now()
        for room, peers in list(self._peers.items()):
            dead = [
                pid for pid, p in peers.items() if now - p.last_seen > self.peer_ttl_s
            ]
            for pid in dead:
                del peers[pid]
                self._subs.get(room, {}).pop(pid, None)
            if not peers:
                del self._peers[room]
                self._subs.pop(room, None)
        self._signals = [
            s for s in self._signals if now - s.created_at <= self.signal_ttl_s
        ]

    def _roster(self, room: str) -> list[dict[str, str]]:
        peers = self._peers.get(room) or {}
        return [
            {"id": p.peer_id, "name": p.name}
            for p in sorted(peers.values(), key=lambda x: x.peer_id)
        ]

    def _fanout(self, room: str, to_peer: str, message: dict[str, Any]) -> None:
        for q in list((self._subs.get(room) or {}).get(to_peer) or []):
            try:
                q.put_nowait(message)
            except Exception:
                pass

    def poll(
        self,
        room: str,
        peer_id: str,
        *,
        name: str = "",
        since: int = 0,
    ) -> dict[str, Any]:
        room = _sanitize_id(room) or DEFAULT_ROOM
        peer_id = _sanitize_id(peer_id)
        if not peer_id:
            raise ValueError("peer_id required")
        with self._lock:
            self._gc()
            peers = self._peers.setdefault(room, {})
            if peer_id not in peers and len(peers) >= self.max_peers:
                raise OverflowError(f"room full (max {self.max_peers} peers)")
            peers[peer_id] = PeerRecord(
                peer_id=peer_id,
                name=(name or peers.get(peer_id, PeerRecord(peer_id)).name)[:64],
                last_seen=_now(),
            )
            roster = self._roster(room)
            inbox = [
                {
                    "id": s.id,
                    "from": s.from_peer,
                    "kind": s.kind,
                    "payload": s.payload,
                }
                for s in self._signals
                if s.room == room and s.to_peer == peer_id and s.id > since
            ]
            inbox.sort(key=lambda x: x["id"])
            # notify others of roster presence (WS)
            for other in peers:
                if other != peer_id:
                    self._fanout(
                        room,
                        other,
                        {"type": "roster", "peers": roster, "room": room},
                    )
            try:
                from ux_channel.realtime.webrtc_metrics import note_poll, note_room_size

                note_poll()
                note_room_size(room, len(roster))
            except Exception:
                pass
            return {
                "ok": True,
                "room": room,
                "peer": peer_id,
                "peers": roster,
                "signals": inbox,
                "server_time": _now(),
            }

    def signal(
        self,
        room: str,
        *,
        from_peer: str,
        to_peer: str,
        kind: str,
        payload: Any,
    ) -> dict[str, Any]:
        room = _sanitize_id(room) or DEFAULT_ROOM
        from_peer = _sanitize_id(from_peer)
        to_peer = _sanitize_id(to_peer)
        kind = (kind or "").lower().strip()
        if kind not in SIGNAL_KINDS:
            raise ValueError(f"kind must be one of {sorted(SIGNAL_KINDS)}")
        if not from_peer or not to_peer:
            raise ValueError("from/to required")
        payload = validate_signal_payload(kind, payload)
        if kind != "ice-done" and _json_size(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload too large")
        with self._lock:
            self._gc()
            peers = self._peers.setdefault(room, {})
            if from_peer not in peers:
                peers[from_peer] = PeerRecord(peer_id=from_peer, last_seen=_now())
            else:
                peers[from_peer].last_seen = _now()
            self._seq += 1
            rec = SignalRecord(
                id=self._seq,
                room=room,
                to_peer=to_peer,
                from_peer=from_peer,
                kind=kind,
                payload=payload,
            )
            self._signals.append(rec)
            msg = {
                "type": "signal",
                "id": rec.id,
                "from": from_peer,
                "kind": kind,
                "payload": payload,
                "room": room,
            }
            self._fanout(room, to_peer, msg)
            try:
                from ux_channel.realtime.webrtc_metrics import note_signal, note_room_size

                note_signal(kind)
                note_room_size(room, len(self._peers.get(room) or {}))
            except Exception:
                pass
            return {"ok": True, "id": rec.id}

    def leave(self, room: str, peer_id: str) -> dict[str, Any]:
        room = _sanitize_id(room) or DEFAULT_ROOM
        peer_id = _sanitize_id(peer_id)
        with self._lock:
            peers = self._peers.get(room)
            if peers and peer_id in peers:
                del peers[peer_id]
            if room in self._subs:
                self._subs[room].pop(peer_id, None)
            roster = self._roster(room)
            for other in list((self._peers.get(room) or {}).keys()):
                self._fanout(
                    room,
                    other,
                    {
                        "type": "peer_left",
                        "peer": peer_id,
                        "peers": roster,
                        "room": room,
                    },
                )
            if peers is not None and not peers:
                self._peers.pop(room, None)
                self._subs.pop(room, None)
            return {"ok": True}

    def subscribe(self, room: str, peer_id: str, q: Any) -> None:
        room = _sanitize_id(room) or DEFAULT_ROOM
        peer_id = _sanitize_id(peer_id)
        with self._lock:
            self._subs.setdefault(room, {}).setdefault(peer_id, []).append(q)

    def unsubscribe(self, room: str, peer_id: str, q: Any) -> None:
        room = _sanitize_id(room) or DEFAULT_ROOM
        peer_id = _sanitize_id(peer_id)
        with self._lock:
            lst = (self._subs.get(room) or {}).get(peer_id) or []
            if q in lst:
                lst.remove(q)
            if not lst and room in self._subs:
                self._subs[room].pop(peer_id, None)


# Tickets (HMAC) — optional door for /rtc


def sign_rtc_ticket(
    config: Any,
    room: str,
    *,
    sub: str = "",
    max_age: int | None = None,
) -> str:
    """Mint short-lived ticket bound to room (+ optional subject)."""
    from itsdangerous import URLSafeTimedSerializer

    secret = getattr(config, "secret", None) or ""
    if not secret:
        raise ValueError("config.secret required to sign RTC tickets")
    age = max_age
    if age is None:
        age = int(getattr(config, "webrtc_ticket_max_age", 300) or 300)
    ser = URLSafeTimedSerializer(str(secret), salt="ux-channel-rtc-v1")
    room_s = _sanitize_id(room) or DEFAULT_ROOM
    sub_s = str(sub or "")[:128]
    return ser.dumps({"room": room_s, "sub": sub_s, "v": 1})


def verify_rtc_ticket(
    config: Any,
    ticket: str,
    room: str,
    *,
    max_age: int | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason)."""
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

    secret = getattr(config, "secret", None) or ""
    if not secret:
        return False, "no secret"
    age = max_age
    if age is None:
        age = int(getattr(config, "webrtc_ticket_max_age", 300) or 300)
    ser = URLSafeTimedSerializer(str(secret), salt="ux-channel-rtc-v1")
    try:
        from ux_channel.devtools.ticket_revoke import get_revocation_list
        if get_revocation_list().is_revoked(ticket):
            return False, "ticket revoked"
    except Exception:
        pass
    try:
        data = ser.loads(ticket, max_age=age)
    except SignatureExpired:
        return False, "ticket expired"
    except BadSignature:
        return False, "invalid ticket"
    want = _sanitize_id(room) or DEFAULT_ROOM
    got = _sanitize_id(str((data or {}).get("room") or ""))
    if got != want:
        return False, "ticket room mismatch"
    # Optional subject bind: if ticket was minted with sub, caller may pass expect_sub
    return True, str((data or {}).get("sub") or "")


# Signaling rate limit (process-local)

_RTC_LIMITER = None
_RTC_LIMITER_LOCK = threading.Lock()


def _rtc_limiter(config: Any = None):
    """Per-process token bucket for /rtc poll+signal."""
    global _RTC_LIMITER
    rpm = 180.0
    burst = 40.0
    if config is not None:
        rpm = float(getattr(config, "webrtc_rate_per_minute", 180) or 180)
        burst = float(getattr(config, "webrtc_rate_burst", 40) or 40)
    if rpm <= 0:
        return None
    with _RTC_LIMITER_LOCK:
        cur = _RTC_LIMITER
        if (
            cur is not None
            and getattr(cur, "_ux_rpm", None) == rpm
            and getattr(cur, "_ux_burst", None) == burst
        ):
            return cur
        from ux_channel.security.ratelimit import MemoryRateLimiter

        lim = MemoryRateLimiter(rate_per_minute=rpm, burst=burst, max_keys=20_000)
        lim._ux_rpm = rpm  # type: ignore[attr-defined]
        lim._ux_burst = burst  # type: ignore[attr-defined]
        _RTC_LIMITER = lim
        return lim


def allow_rtc_traffic(
    config: Any,
    *,
    peer: str,
    room: str = "",
    cost: float = 1.0,
    client_key: str = "",
) -> tuple[bool, str]:
    """Return (True, "") if within per-peer signaling budget."""
    lim = _rtc_limiter(config)
    if lim is None:
        return True, ""
    peer_s = _sanitize_id(peer) or "unknown"
    room_s = _sanitize_id(room) or DEFAULT_ROOM
    ck = _sanitize_id(client_key) if client_key else ""
    key = f"rtc:{(ck + ':') if ck else ''}{room_s}:{peer_s}"
    if lim.allow(key, cost=cost):
        return True, ""
    try:
        from ux_channel.realtime.webrtc_metrics import note_auth_fail

        note_auth_fail()
    except Exception:
        pass
    return False, "rate limited"


def authorize_rtc(
    config: Any,
    room: str,
    *,
    ticket: str | None = None,
    origin: str | None = None,
    host: str | None = None,
) -> tuple[bool, str]:
    """
    Gate /rtc access.

    * ``webrtc_require_origin`` → same origin policy as actions
    * ``webrtc_require_ticket`` → valid HMAC ticket for room
    """
    if config is None:
        return True, ""
    if getattr(config, "webrtc_require_origin", False):
        from ux_channel.security.security import origin_allowed

        if not origin_allowed(
            origin,
            allowed_origins=tuple(getattr(config, "allowed_origins", ()) or ()),
            enforce_same_origin=bool(getattr(config, "enforce_same_origin", True)),
            request_host=host,
        ):
            return False, "origin not allowed"
    if getattr(config, "webrtc_require_ticket", False):
        if not ticket:
            try:
                from ux_channel.realtime.webrtc_metrics import note_auth_fail

                note_auth_fail()
            except Exception:
                pass
            return False, "rtc ticket required"
        ok, detail = verify_rtc_ticket(config, ticket, room)
        if not ok:
            try:
                from ux_channel.realtime.webrtc_metrics import note_auth_fail

                note_auth_fail()
            except Exception:
                pass
            return False, detail or "invalid ticket"
        return True, ""
    return True, ""


# Process singleton

_STORE: "MemoryRtcStore | Any | None" = None
_STORE_LOCK = threading.Lock()


_STORE_FP: tuple | None = None


def _rtc_store_fingerprint(config: Any) -> tuple:
    max_peers = 8
    peer_ttl = 30.0
    sig_ttl = 60.0
    redis_url = ""
    use_redis = False
    if config is not None:
        max_peers = int(getattr(config, "webrtc_max_peers", 8) or 8)
        peer_ttl = float(getattr(config, "webrtc_peer_ttl_s", 30) or 30)
        sig_ttl = float(getattr(config, "webrtc_signal_ttl_s", 60) or 60)
        redis_url = str(getattr(config, "redis_url", None) or "")
        flag = getattr(config, "webrtc_use_redis", None)
        if flag is None:
            use_redis = bool(redis_url)
        else:
            use_redis = bool(flag) and bool(redis_url)
    kind = "redis" if (use_redis and redis_url) else "memory"
    return (kind, max_peers, peer_ttl, sig_ttl, redis_url)


def get_rtc_store(config: Any = None) -> Any:
    """Return process store (Memory) or Redis when configured.

    Rebuilds when config fingerprint changes (max_peers / redis_url / TTLs).

    Redis path (multi-worker)::

        ChannelConfig(..., redis_url=os.environ["REDIS_URL"], webrtc_use_redis=True)
    """
    global _STORE, _STORE_FP
    fp = _rtc_store_fingerprint(config)
    with _STORE_LOCK:
        if _STORE is not None and _STORE_FP == fp:
            return _STORE
        kind, max_peers, peer_ttl, sig_ttl, redis_url = fp
        if kind == "redis" and redis_url:
            try:
                from ux_channel.redis_extra import RedisRtcStore

                _STORE = RedisRtcStore(
                    redis_url,
                    peer_ttl_s=peer_ttl,
                    signal_ttl_s=sig_ttl,
                    max_peers=max_peers,
                )
                _STORE_FP = fp
                return _STORE
            except Exception:
                pass  # fall back to memory
        _STORE = MemoryRtcStore(
            peer_ttl_s=peer_ttl,
            signal_ttl_s=sig_ttl,
            max_peers=max_peers,
        )
        _STORE_FP = fp
        return _STORE


def reset_rtc_store() -> None:
    global _STORE, _STORE_FP
    with _STORE_LOCK:
        _STORE = None
        _STORE_FP = None


def webrtc_enabled(config: Any) -> bool:
    if config is None:
        return True
    return bool(getattr(config, "webrtc_enabled", True))


# ICE — one rule, two places (low cognitive load)
#
#   html  →  STUN only (safe in data-* / plugin client seed)
#   live  →  STUN + short-lived TURN (after ticket / server auth only)
#
# Application: just call ch.webrtc.plugin(...) — both are wired for you.
# Power: ch.webrtc.ice.servers() / ch.webrtc.ice.live(sub=...) / ch.webrtc.ice.url
#

@dataclass
class IceAccess:
    """
    ICE placement helper attached as ``ch.webrtc.ice``.

    **Rule (only this):**

    * ``servers()`` — may go in attributes, SSR, CDN HTML
    * ``live(sub=…)`` — server join handlers or ``GET ice.url`` only
    * ``url`` — browser fetches live ICE with the room ticket

    You never choose "where do TURN passwords go?" — they only appear in ``live``.
    """

    plane: Any

    def servers(self) -> list[dict[str, Any]]:
        """Public ICE (STUN / credential-free). Safe in data-* / client seed."""
        return self.plane.public_ice_servers()

    def live(
        self,
        *,
        sub: str = "uid",
        ttl_s: int | None = None,
        include_turn: bool = True,
    ) -> list[dict[str, Any]]:
        """Authenticated ICE (may include short-lived TURN). Not for HTML attrs."""
        return self.plane.ice_servers(sub=sub, ttl_s=ttl_s, include_turn=include_turn)

    @property
    def url(self) -> str:
        """Path for ticketed ``GET`` (client ``iceUrl``)."""
        return f"{self.plane.path}/ice"

    def posture(self) -> dict[str, Any]:
        return self.plane.turn_posture()


# Channel façade


@dataclass
class WebRTCPlane:
    """
    P2P plane attached as ``ch.webrtc`` after ``Channel.boot``.

    Application (only these)
    ------------------
    * ``enabled`` / ``path`` / ``ws_path`` — signaling endpoints
    * ``sign_ticket(room)`` — mint room door for private rooms
    * ``session(room, ...).plugin()`` — **placement bag** (scripts, attrs, client)
    * ``ice`` — ``ice.servers()`` / ``ice.live()`` / ``ice.url`` (one ICE rule)
    * ``body_attrs(room=...)`` — data-* for the HTML body
    * ``diagnose()`` — health + security posture

    Does **not** ship call UI (video tags, CSS, chat widgets) — that is the host app.

    Advanced (hosts / tests)
    ------------------------
    ``store()``, ``script_src``, ``script_tag``, ``default_ice_servers``,
    ``public_ice_servers()`` (HTML-safe STUN only).
    Prefer ``ch.runtime()`` + ``ch.body_attrs(webrtc=...)`` (demo: script_tags / attr_string).

    Not here
    --------
    Media bytes, SFU, WHIP — see ``ux_channel.sfu`` / ``ux_channel.whip``.
    """

    channel: Any

    @property
    def enabled(self) -> bool:
        cfg = getattr(self.channel, "config", None)
        if cfg is None:
            return True
        return bool(getattr(cfg, "webrtc_enabled", True))

    @property
    def ice(self) -> IceAccess:
        """ICE placement: ``ice.servers()`` vs ``ice.live()`` — see :class:`IceAccess`."""
        return IceAccess(self)

    @property
    def path(self) -> str:
        base = str(getattr(self.channel, "path", "/ux-channel")).rstrip("/")
        return f"{base}/rtc"

    @property
    def ws_path(self) -> str:
        return f"{self.path}/ws"

    @property
    def script_src(self) -> str:
        base = str(getattr(self.channel, "path", "/ux-channel")).rstrip("/")
        return f"{base}/static/ux-webrtc.js"

    def store(self) -> Any:
        """Advanced: process/Redis signaling store (tests/hosts)."""
        return get_rtc_store(getattr(self.channel, "config", None))

    def script_tag(self) -> str:
        if not self.enabled:
            return ""
        return f'<script src="{self.script_src}" defer></script>'

    def sign_ticket(self, room: str = DEFAULT_ROOM, *, sub: str = "") -> str:
        return sign_rtc_ticket(self.channel.config, room, sub=sub)

    def issue_membership(
        self,
        room: str = DEFAULT_ROOM,
        *,
        sub: str = "",
        scopes: Any = (),
        trust: Any = None,
        max_age: int | None = None,
    ) -> Any:
        """
        Mint RTC + workplace tickets for a policy-shaped room (power helper).

        Lazy-imports ``ux_channel.workplace.mesh`` — core media path unchanged
        if you only call ``sign_ticket``.
        """
        from ux_channel.workplace import issue_mesh_membership

        return issue_mesh_membership(
            self.channel,
            room,
            sub=sub,
            scopes=scopes or (),
            trust=trust,
            max_age=max_age,
        )

    def workplace_from_ticket(
        self,
        rtc_ticket: str,
        room: str,
        *,
        scopes: Any = (),
        peer_id: str | None = None,
        attach: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Bind Workplace from RTC ticket + server scopes (lazy import)."""
        from ux_channel.workplace import workplace_from_rtc

        return workplace_from_rtc(
            self.channel,
            rtc_ticket,
            room,
            scopes=scopes or (),
            peer_id=peer_id,
            attach=attach,
            **kwargs,
        )

    def default_ice_servers(self) -> list[dict[str, Any]]:
        """
        STUN by default; optional TURN from env / config.

        Env (comma-separated URLs)::

            UX_CHANNEL_TURN_URLS=turn:turn.example.com:3478
            UX_CHANNEL_TURN_USER=u
            UX_CHANNEL_TURN_PASS=p
        """
        import os

        servers: list[dict[str, Any]] = [{"urls": "stun:stun.l.google.com:19302"}]
        cfg = getattr(self.channel, "config", None)
        # config.webrtc_ice_servers if set
        extra = getattr(cfg, "webrtc_ice_servers", None) if cfg else None
        if extra:
            servers = list(extra)
        urls = os.environ.get("UX_CHANNEL_TURN_URLS") or ""
        user = os.environ.get("UX_CHANNEL_TURN_USER") or ""
        password = os.environ.get("UX_CHANNEL_TURN_PASS") or ""
        if urls:
            for u in urls.split(","):
                u = u.strip()
                if not u:
                    continue
                entry: dict[str, Any] = {"urls": u}
                if user:
                    entry["username"] = user
                    entry["credential"] = password
                servers.append(entry)
        return servers

    def public_ice_servers(self) -> list[dict[str, Any]]:
        """Alias of ``ice.servers()`` — STUN only; safe in HTML.

        Prefer ``ch.webrtc.ice.servers()`` in new code (same implementation).
        """
        out: list[dict[str, Any]] = []
        for s in self.default_ice_servers():
            if not isinstance(s, dict):
                continue
            if s.get("credential") or s.get("username"):
                continue
            urls = s.get("urls")
            if not urls:
                continue
            out.append({"urls": urls})
        if not out:
            out = [{"urls": "stun:stun.l.google.com:19302"}]
        return out

    def ice_servers(
        self,
        *,
        sub: str = "uid",
        ttl_s: int | None = None,
        include_turn: bool = True,
    ) -> list[dict[str, Any]]:
        """Alias of ``ice.live(sub=…)`` — may include short-lived TURN.

        Prefer ``ch.webrtc.ice.live(sub=…)``. Never assign this to HTML data-*.
        """
        pub = self.public_ice_servers()
        if not include_turn:
            return pub
        from ux_channel.realtime.webrtc_turn import ice_servers_with_turn

        return ice_servers_with_turn(stun=pub, username=sub or "uid", ttl_s=ttl_s)

    def turn_posture(self) -> dict[str, Any]:
        """TURN config summary (no secrets)."""
        from ux_channel.realtime.webrtc_turn import turn_configured

        return turn_configured()

    def body_attrs(
        self,
        *,
        room: str = DEFAULT_ROOM,
        auto: bool = False,
        media: bool | str = False,
        ticket: str | None = None,
        prefer_ws: bool = True,
    ) -> dict[str, str]:
        if not self.enabled:
            return {}
        attrs = {
            "data-channel-webrtc-rtc": self.path,
            "data-channel-webrtc-room": _sanitize_id(room) or DEFAULT_ROOM,
        }
        if prefer_ws:
            attrs["data-channel-webrtc-ws"] = self.ws_path
        if auto:
            attrs["data-channel-webrtc-auto"] = ""
        if media:
            attrs["data-channel-webrtc-media"] = "av" if media is True else str(media)
        if ticket:
            attrs["data-channel-webrtc-ticket"] = ticket
        # ICE rule: html blob = ice.servers(); fetch path = ice.url (live TURN)
        try:
            attrs["data-channel-webrtc-ice"] = _serde.dumps(
                self.ice.servers(), separators=(",", ":")
            )
        except Exception:
            pass
        attrs["data-channel-webrtc-ice-url"] = self.ice.url
        return attrs


    # --- plugin DX (no UI chrome) -----------------------------------------

    def session(
        self,
        room: str = DEFAULT_ROOM,
        *,
        ticket: str | None = None,
        sub: str = "",
        media: Any = "none",
        auto_media: bool = False,
        simulcast: bool = False,
        ice_policy: str = "all",
        **extra_client: Any,
    ) -> Any:
        """
        Room-scoped **plugin** handle — tickets + placement, not markup.

        ::

            p = ch.webrtc.session("lobby", sub=user_id).plugin()
            # host places p.scripts_html, p.attr_string; joins with p.client
        """
        from ux_channel.realtime.webrtc_ui import RtcSession

        return RtcSession(
            plane=self,
            room=room or DEFAULT_ROOM,
            ticket=ticket,
            sub=sub,
            media=media,
            auto_media=auto_media,
            simulcast=bool(simulcast),
            ice_policy="relay" if ice_policy == "relay" else "all",
            extra_client=dict(extra_client),
        )

    def plugin(
        self,
        room: str = DEFAULT_ROOM,
        *,
        ticket: str | None = None,
        sub: str = "",
        inspector: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Shortcut: ``session(...).plugin()`` — bag for any UI host."""
        return self.session(room, ticket=ticket, sub=sub, **kwargs).plugin(
            inspector=inspector
        )

    def diagnose(self) -> dict[str, Any]:

        """Health + security posture (no secrets)."""
        cfg = getattr(self.channel, "config", None)
        return {
            "enabled": self.enabled,
            "path": self.path,
            "ws_path": self.ws_path,
            "script": self.script_src,
            "max_peers": getattr(cfg, "webrtc_max_peers", 8) if cfg else 8,
            "require_ticket": bool(
                getattr(cfg, "webrtc_require_ticket", False) if cfg else False
            ),
            "require_origin": bool(
                getattr(cfg, "webrtc_require_origin", False) if cfg else False
            ),
            "rate_per_minute": int(
                getattr(cfg, "webrtc_rate_per_minute", 180) or 0
            )
            if cfg
            else 180,
            "min_peer_len": int(getattr(cfg, "webrtc_min_peer_len", 1) or 1)
            if cfg
            else 1,
            "ice_servers": len(self.default_ice_servers()),
            "public_ice_servers": len(self.public_ice_servers()),
            "kinds": sorted(SIGNAL_KINDS),
            "store": type(self.store()).__name__,
            "metrics": __import__(
                "ux_channel.realtime.webrtc_metrics", fromlist=["rtc_metrics"]
            ).rtc_metrics.snapshot(),
            "use_redis": bool(getattr(cfg, "webrtc_use_redis", None) if cfg else False),
            "dtls_pinning": False,  # browser WebRTC: not available to apps
            "security": {
                "tickets": bool(
                    getattr(cfg, "webrtc_require_ticket", False) if cfg else False
                ),
                "origin": bool(
                    getattr(cfg, "webrtc_require_origin", False) if cfg else False
                ),
                "html_ice_has_credentials": False,
                "dtls_cert_pinning": "unsupported_in_browser_webrtc",
                "turn": self.turn_posture(),
                "ice_endpoint": f"{self.path}/ice",
            },
        }


def attach_webrtc(channel: Any) -> None:
    channel.webrtc = WebRTCPlane(channel)


__all__ = [
    "DEFAULT_ROOM",
    "SIGNAL_KINDS",
    "validate_signal_payload",
    "PeerRecord",
    "SignalRecord",
    "MemoryRtcStore",
    "WebRTCPlane",
    "IceAccess",
    "RtcStore",
    "get_rtc_store",
    "reset_rtc_store",
    "new_peer_id",
    "sign_rtc_ticket",
    "verify_rtc_ticket",
    "authorize_rtc",
    "allow_rtc_traffic",
    "attach_webrtc",
    "webrtc_enabled",
]
