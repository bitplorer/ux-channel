"""
Short-lived TURN credentials (coturn REST / static-auth-secret).

Mission
-------
Never put long-lived TURN passwords in HTML. Mint time-bound credentials
server-side (or via authenticated ``GET /ux-channel/rtc/ice``).

Coturn ``use-auth-secret`` / REST API shape (widely deployed)::

    username = f"{expiry_unix}:{user_id}"
    credential = base64(hmac_sha1(static_auth_secret, username))

Env
---
* ``UX_CHANNEL_TURN_URLS`` — comma-separated turn: / turns: URLs
* ``UX_CHANNEL_TURN_SECRET`` — coturn static-auth-secret (preferred)
* ``UX_CHANNEL_TURN_TTL`` — seconds (default 300)
* Discouraged static TURN creds: ``UX_CHANNEL_TURN_USER`` + ``UX_CHANNEL_TURN_PASS``
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Any, Optional

__all__ = [
    "turn_urls_from_env",
    "mint_turn_credential",
    "ice_servers_with_turn",
    "turn_configured",
]


def turn_urls_from_env() -> list[str]:
    raw = os.environ.get("UX_CHANNEL_TURN_URLS") or ""
    return [u.strip() for u in raw.split(",") if u.strip()]


def turn_configured() -> dict[str, Any]:
    """Posture without secrets."""
    urls = turn_urls_from_env()
    secret = bool(os.environ.get("UX_CHANNEL_TURN_SECRET"))
    static_user = bool(os.environ.get("UX_CHANNEL_TURN_USER"))
    mode = "none"
    if urls and secret:
        mode = "rest"
    elif urls and static_user:
        mode = "static"  # long-lived — avoid in HTML
    elif urls:
        mode = "urls_only"
    return {
        "mode": mode,
        "urls": len(urls),
        "rest_secret": secret,
        "static_userpass": static_user,
    }


def mint_turn_credential(
    *,
    secret: str,
    username: str = "uid",
    ttl_s: int = 300,
    now: Optional[float] = None,
) -> tuple[str, str, int]:
    """
    Return ``(turn_username, turn_credential, expires_at_unix)``.

    Compatible with coturn ``static-auth-secret`` / REST TURN.
    """
    if not secret:
        raise ValueError("TURN secret required")
    ttl_s = max(30, min(int(ttl_s), 86400))
    exp = int((now if now is not None else time.time()) + ttl_s)
    # strip odd characters from user part
    user = "".join(c for c in str(username or "uid") if c.isalnum() or c in "-_.@")[:64] or "uid"
    turn_user = f"{exp}:{user}"
    digest = hmac.new(
        secret.encode("utf-8"),
        turn_user.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    cred = base64.b64encode(digest).decode("ascii")
    return turn_user, cred, exp


def ice_servers_with_turn(
    *,
    stun: Optional[list[dict[str, Any]]] = None,
    turn_urls: Optional[list[str]] = None,
    username: str = "uid",
    ttl_s: int | None = None,
    secret: Optional[str] = None,
    allow_static_userpass: bool = True,
) -> list[dict[str, Any]]:
    """
    Build ICE list: STUN (+ optional short-lived or static TURN).

    Prefer ``UX_CHANNEL_TURN_SECRET`` over long-lived USER/PASS.
    """
    servers: list[dict[str, Any]] = list(
        stun
        or [{"urls": "stun:stun.l.google.com:19302"}]
    )
    urls = turn_urls if turn_urls is not None else turn_urls_from_env()
    if not urls:
        return servers

    if ttl_s is None:
        try:
            ttl_s = int(os.environ.get("UX_CHANNEL_TURN_TTL") or "300")
        except ValueError:
            ttl_s = 300

    sec = secret if secret is not None else (os.environ.get("UX_CHANNEL_TURN_SECRET") or "")
    if sec:
        u, c, _exp = mint_turn_credential(secret=sec, username=username, ttl_s=ttl_s)
        for url in urls:
            servers.append({"urls": url, "username": u, "credential": c})
        return servers

    if allow_static_userpass:
        user = os.environ.get("UX_CHANNEL_TURN_USER") or ""
        password = os.environ.get("UX_CHANNEL_TURN_PASS") or ""
        if user:
            for url in urls:
                servers.append(
                    {"urls": url, "username": user, "credential": password}
                )
    return servers
