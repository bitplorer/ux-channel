"""WebSocket authorization — production doors for ``WS /ux-channel/ws``.
SSE push is one-way. WebSockets add duplex traffic (subscribe + optional Intent
dispatch). Security must cover:
1. **Connect-time auth** — same ticket / push_token / public policy as SSE
2. **Origin** — browsers send Origin on WS; reject cross-site when configured
3. **Per-topic subscribe** — re-check on each ``subscribe``…"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from ux_channel.security.push_security import (
    authorize_push_subscribe,
    extract_push_credentials,
    validate_topic,
    PushAuthError,
)
from ux_channel.security.security import origin_allowed


def check_ws_origin(
    origin: Optional[str],
    *,
    config: Any = None,
    request_host: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    WebSocket Origin policy.

    - Production + enforce_same_origin / allowed_origins: use origin_allowed
    - Origin \"null\" denied by origin_allowed
    - Missing Origin: allowed for non-browser clients unless
      ``ws_require_origin=True``
    """
    require = False
    if config is not None:
        require = bool(getattr(config, "ws_require_origin", False))
        # production default: require origin when enforce_same_origin and browser-like
        if (
            getattr(config, "ws_require_origin", None) is None
            and getattr(config, "environment", "") == "production"
            and bool(getattr(config, "enforce_same_origin", True))
        ):
            # still allow missing Origin for service clients; optional strict flag
            require = bool(getattr(config, "ws_require_origin", False))

    if require and not origin:
        return False, "origin required"

    allowed = tuple(getattr(config, "allowed_origins", ()) or ()) if config else ()
    enforce = bool(getattr(config, "enforce_same_origin", True)) if config else True
    if origin_allowed(
        origin,
        allowed_origins=allowed,
        enforce_same_origin=enforce,
        request_host=request_host,
    ):
        return True, "ok"
    return False, "origin not allowed"


def authorize_ws_connect(
    config: Any,
    *,
    token: Optional[str] = None,
    ticket: Optional[str] = None,
    bearer: Optional[str] = None,
    initial_topics: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """
    Gate the WebSocket handshake.

    If ``initial_topics`` provided, every topic must pass subscribe auth.
    If no topics yet, require either:
      - not push_require_auth (dev open), or
      - valid ticket/token, or
      - push_open
    so anonymous sockets cannot linger for private intent abuse without creds
    when production fail-closed.
    """
    topics = [t for t in (initial_topics or ()) if t]
    if topics:
        for t in topics:
            try:
                validate_topic(
                    t,
                    max_len=int(getattr(config, "push_topic_max_len", 128) or 128)
                    if config
                    else 128,
                )
            except PushAuthError as exc:
                return False, str(exc)
            ok, reason = authorize_push_subscribe(
                config, t, token=token, ticket=ticket, bearer=bearer
            )
            if not ok:
                return False, reason
        return True, "topics_ok"

    # No topics at connect — still need connect credential in production
    if config is None:
        return True, "no_config"

    if getattr(config, "push_open", False):
        return True, "push_open"

    # ticket/token alone grants connect (scoped ticket may be topic-bound;
    # topic checked again on subscribe)
    if ticket:
        # ticket must be well-formed; topic checked on subscribe
        from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
        from ux_channel.security.push_security import _PUSH_SALT, _serializer

        secret = getattr(config, "secret", None)
        if not secret:
            return False, "push tickets not configured"
        age = int(getattr(config, "push_ticket_max_age", 300) or 300)
        try:
            _serializer(str(secret)).loads(ticket, max_age=age)
            return True, "ticket"
        except SignatureExpired:
            return False, "push ticket expired"
        except BadSignature:
            # try previous secrets
            for prev in getattr(config, "previous_secrets", ()) or ():
                if not prev or len(str(prev)) < 16:
                    continue
                try:
                    _serializer(str(prev)).loads(ticket, max_age=age)
                    return True, "ticket"
                except Exception:
                    continue
            return False, "push ticket invalid"

    if token or bearer:
        import hmac

        expected = getattr(config, "push_token", None)
        cred = token or bearer
        if expected and cred and hmac.compare_digest(str(expected), str(cred)):
            return True, "push_token"
        if expected:
            return False, "push token invalid"
        # token provided but none configured — ignore, fall through

    require = getattr(config, "push_require_auth", None)
    if require is None:
        require = getattr(config, "environment", "production") == "production"
    # Also: if push_token configured, require it for connect without topics
    if getattr(config, "push_token", None) and not (token or bearer or ticket):
        return False, "push token required"

    if not require:
        return True, "auth_not_required"
    return False, "websocket authorization required"


def authorize_ws_subscribe(
    config: Any,
    topic: str,
    *,
    token: Optional[str] = None,
    ticket: Optional[str] = None,
    bearer: Optional[str] = None,
) -> Tuple[bool, str]:
    """Per-message subscribe authorization (same policy as SSE topic)."""
    return authorize_push_subscribe(
        config, topic, token=token, ticket=ticket, bearer=bearer
    )


def parse_topics_param(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).split(",") if p.strip()]
