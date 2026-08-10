"""
SFU adapter surface (P2) — pluggable bridge to external media servers.

uxchannel mesh (``/rtc``) stays for small rooms. For large meetings, point
clients at an SFU. This module defines a **stable interface** so apps do not
hard-code LiveKit/mediasoup URLs in business logic.

Example stub::

    from ux_channel.realtime.sfu import SfuConfig, NullSfu, LiveKitSfu

    sfu = LiveKitSfu(SfuConfig(url=os.environ["LIVEKIT_URL"], api_key=..., api_secret=...))
    token = sfu.create_token(room="lobby", identity=user_id)

Application Developer tooling (preferred)::

    p = ch.media.plugin("lobby", sub=user_id)  # auto mesh|sfu
    p = ch.media.plugin("lobby", sub=user_id, mode="sfu")
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass
class SfuConfig:
    """Connection details for an external SFU."""

    url: str = ""
    api_key: str = ""
    api_secret: str = ""
    # optional default room prefix
    room_prefix: str = ""


class SfuAdapter(Protocol):
    def create_token(
        self,
        *,
        room: str,
        identity: str,
        name: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
        ttl_s: int = 3600,
    ) -> str: ...

    def room_url(self, room: str) -> str: ...


class NullSfu:
    """No-op SFU — raises if used for tokens (forces explicit config)."""

    def __init__(self, config: SfuConfig | None = None) -> None:
        self.config = config or SfuConfig()

    def create_token(self, **kwargs: Any) -> str:
        raise RuntimeError(
            "No SFU configured. Set LiveKit/mediasoup credentials or use mesh /rtc."
        )

    def room_url(self, room: str) -> str:
        return ""


class LiveKitSfu:
    """
    LiveKit token helper (optional dependency ``livekit-api`` or JWT via PyJWT).

    If ``livekit`` package is missing, falls back to a documented JWT shape when
    ``PyJWT`` is installed; otherwise raises ImportError with install hint.
    """

    def __init__(self, config: SfuConfig) -> None:
        if not config.url or not config.api_key or not config.api_secret:
            raise ValueError("LiveKitSfu requires url, api_key, api_secret")
        self.config = config

    def room_url(self, room: str) -> str:
        base = self.config.url.rstrip("/")
        return f"{base}"

    def create_token(
        self,
        *,
        room: str,
        identity: str,
        name: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
        ttl_s: int = 3600,
    ) -> str:
        room = f"{self.config.room_prefix}{room}"
        try:
            from livekit import api  # type: ignore

            grants = api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=can_publish,
                can_subscribe=can_subscribe,
            )
            token = (
                api.AccessToken(self.config.api_key, self.config.api_secret)
                .with_identity(identity)
                .with_name(name or identity)
                .with_grants(grants)
                .with_ttl(ttl_s)
            )
            return token.to_jwt()
        except ImportError:
            pass
        # Minimal JWT fallback (HS256) — LiveKit-compatible claims subset
        try:
            import jwt  # type: ignore
            import time

            now = int(time.time())
            payload = {
                "iss": self.config.api_key,
                "sub": identity,
                "nbf": now,
                "exp": now + int(ttl_s),
                "name": name or identity,
                "video": {
                    "roomJoin": True,
                    "room": room,
                    "canPublish": can_publish,
                    "canSubscribe": can_subscribe,
                },
            }
            return jwt.encode(payload, self.config.api_secret, algorithm="HS256")
        except ImportError:
            pass
        # Stdlib HS256 JWT (no extra deps) — LiveKit video grant claims
        import base64
        import hashlib
        import hmac
        import time as _time

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        now = int(_time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self.config.api_key,
            "sub": identity,
            "nbf": now,
            "exp": now + int(ttl_s),
            "name": name or identity,
            "video": {
                "roomJoin": True,
                "room": room,
                "canPublish": can_publish,
                "canSubscribe": can_subscribe,
            },
        }
        import json as _json

        h = _b64url(_serde.dumps(header).encode())
        pld = _b64url(_serde.dumps(payload).encode())
        sig = hmac.new(
            self.config.api_secret.encode("utf-8"),
            f"{h}.{pld}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{h}.{pld}.{_b64url(sig)}"


def get_sfu(config: Any = None) -> SfuAdapter:
    """Factory from ChannelConfig fields ``sfu_provider``, ``sfu_url``, …"""
    if config is None:
        return NullSfu()
    provider = (getattr(config, "sfu_provider", None) or "none").lower()
    if provider in ("", "none", "mesh"):
        return NullSfu()
    cfg = SfuConfig(
        url=str(getattr(config, "sfu_url", "") or ""),
        api_key=str(getattr(config, "sfu_api_key", "") or ""),
        api_secret=str(getattr(config, "sfu_api_secret", "") or ""),
        room_prefix=str(getattr(config, "sfu_room_prefix", "") or ""),
    )
    if provider == "livekit":
        return LiveKitSfu(cfg)
    raise ValueError(
        f"Unknown sfu_provider {provider!r}. Supported: none|mesh|livekit"
    )


__all__ = [
    "SfuConfig",
    "SfuAdapter",
    "NullSfu",
    "LiveKitSfu",
    "get_sfu",
    "handle_sfu_token",
]


def handle_sfu_token(
    config: Any,
    body: dict[str, Any] | None,
    *,
    ticket: str | None = None,
    origin: str | None = None,
    host: str | None = None,
    client_key: str = "",
) -> tuple[int, dict[str, Any]]:
    """
    Production-safe SFU join-token mint.

    Same mental gate as mesh RTC where applicable:
    * origin when ``webrtc_require_origin``
    * room ticket when ``webrtc_require_ticket`` (or ``sfu_require_ticket``)
    * rate limit via RTC limiter
    * rejects empty/anon identity in production
    """
    body = body or {}
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "object required"}

    provider = (getattr(config, "sfu_provider", None) or "none").lower()
    if provider in ("", "none", "mesh"):
        return 501, {"ok": False, "error": "sfu not configured"}

    room = str(body.get("room") or "default").strip() or "default"
    identity = str(body.get("identity") or "").strip()
    name = str(body.get("name") or identity)
    env = str(getattr(config, "environment", "development") or "development")

    if not identity or identity.lower() in ("anon", "anonymous", "null", "undefined"):
        if env == "production":
            return 400, {"ok": False, "error": "identity required"}
        identity = identity or "anon"

    # Reuse RTC origin/ticket gate (media join is as sensitive as mesh)
    from ux_channel.realtime.webrtc import authorize_rtc, allow_rtc_traffic, _sanitize_id

    require_ticket = bool(
        getattr(config, "sfu_require_ticket", None)
        if getattr(config, "sfu_require_ticket", None) is not None
        else getattr(config, "webrtc_require_ticket", False)
    )
    # Temporary shadow config-like: authorize_rtc reads webrtc_require_*
    # If only sfu_require_ticket is set, force ticket check manually.
    tok = ticket or (str(body.get("ticket")) if body.get("ticket") else None)
    ok, reason = authorize_rtc(config, room, ticket=tok, origin=origin, host=host)
    if not ok:
        return 403, {"ok": False, "error": reason or "unauthorized"}
    if tok:
        from ux_channel.realtime.webrtc import verify_rtc_ticket

        ok_t, sub_or_reason = verify_rtc_ticket(config, tok, room)
        if not ok_t:
            return 403, {"ok": False, "error": sub_or_reason or "invalid ticket"}
        # Ticket subject bind: non-empty sub must match identity
        if sub_or_reason and identity and sub_or_reason != identity:
            return 403, {"ok": False, "error": "ticket subject mismatch"}
    # When sfu_require_ticket=True but webrtc tickets are off, enforce here.
    if require_ticket and not getattr(config, "webrtc_require_ticket", False):
        if not tok:
            return 403, {"ok": False, "error": "ticket required"}
        from ux_channel.realtime.webrtc import verify_rtc_ticket

        ok_t, reason_t = verify_rtc_ticket(config, tok, room)
        if not ok_t:
            return 403, {"ok": False, "error": reason_t or "invalid ticket"}

    peer_key = _sanitize_id(identity) or "anon"
    allowed, why = allow_rtc_traffic(
        config, peer=peer_key, room=room, cost=3.0, client_key=client_key
    )
    if not allowed:
        return 429, {"ok": False, "error": why or "rate limited"}

    try:
        sfu = get_sfu(config)
        token = sfu.create_token(
            room=room,
            identity=identity,
            name=name,
            can_publish=bool(body.get("can_publish", True)),
            can_subscribe=bool(body.get("can_subscribe", True)),
            ttl_s=int(body.get("ttl_s") or 3600),
        )
        return 200, {
            "ok": True,
            "token": token,
            "url": sfu.room_url(room),
            "room": room,
            "identity": identity,
            "provider": provider,
        }
    except RuntimeError as exc:
        return 501, {"ok": False, "error": str(exc)}
    except Exception as exc:
        return 500, {"ok": False, "error": "sfu token mint failed"}
