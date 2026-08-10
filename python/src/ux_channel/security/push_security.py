"""SSE / push subscribe authorization — production-ready doors for GET /push/{topic}.
POST /action is gated by caps, CSRF header, origin, and optional auth.
GET /push/{topic} is a long-lived stream and previously only had an optional
shared ``push_token``. That is not enough for production private boards.
This module provides:
1. **Topic validation** — reject empty, oversized, or path-like…"""

from __future__ import annotations

import re
import time
from typing import Any, Mapping, Optional, Sequence, Tuple

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ux_channel.protocol.errors import ChannelError

# Topics: start alphanumeric; then alnum, dot, underscore, colon, hyphen
_TOPIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:|-]{0,127}$")
_PUSH_SALT = "ux-channel-push-ticket"


class PushAuthError(ChannelError):
    """Subscribe denied or ticket invalid."""


def _ticket_not_revoked(ticket: str | None) -> tuple[bool, str]:
    if not ticket:
        return True, "ok"
    try:
        from ux_channel.devtools.ticket_revoke import get_revocation_list
        if get_revocation_list().is_revoked(ticket):
            return False, "push ticket revoked"
    except Exception:
        pass
    return True, "ok"


def _emit_push_deny(topic: str, reason: str) -> None:
    try:
        from ux_channel.security.security_events import emit_security
        emit_security("push_deny", topic=str(topic or ""), reason=str(reason or ""))
    except Exception:
        pass


def _tenant_and_policy(config: Any, topic: str, *, sub: Any = None) -> tuple[bool, str]:
    """Enforce tenant_topic_prefix + PolicyEngine.check_topic when configured."""
    if config is not None:
        prefix = str(getattr(config, "tenant_topic_prefix", "") or "")
        if prefix and not topic_is_public(topic, config):
            if not str(topic).startswith(prefix):
                return False, f"topic must start with tenant prefix {prefix!r}"
    try:
        from ux_channel.security.policy import get_policy
        eng = get_policy()
        if eng is not None:
            ok, reason = eng.check_topic(topic, sub)
            if not ok:
                return False, reason or "policy denied topic"
    except Exception:
        pass
    return True, "ok"


def normalize_topic(topic: str) -> str:
    return (topic or "").strip()


def validate_topic(
    topic: str,
    *,
    max_len: int = 128,
) -> str:
    """
    Return normalized topic or raise PushAuthError.
    """
    t = normalize_topic(topic)
    if not t:
        raise PushAuthError("empty push topic")
    if len(t) > max_len:
        raise PushAuthError("push topic too long")
    if ".." in t or "/" in t or "\\" in t or "\x00" in t:
        raise PushAuthError("invalid push topic")
    if not _TOPIC_RE.match(t):
        raise PushAuthError("invalid push topic characters")
    return t


def _prefixes(config: Any) -> tuple[str, ...]:
    raw = getattr(config, "push_public_prefixes", None) if config is not None else None
    if raw is None:
        return ("public.",)
    if isinstance(raw, str):
        return tuple(p.strip() for p in raw.split(",") if p.strip())
    return tuple(str(p) for p in raw)


def topic_is_public(topic: str, config: Any = None) -> bool:
    """True if topic matches a configured public prefix."""
    try:
        t = validate_topic(topic, max_len=int(getattr(config, "push_topic_max_len", 128) or 128))
    except PushAuthError:
        return False
    for pref in _prefixes(config):
        if pref and t.startswith(pref):
            return True
    return False


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt=_PUSH_SALT)


def sign_push_ticket(
    config: Any,
    topic: str,
    *,
    sub: Optional[str] = None,
    max_age: Optional[int] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Mint a short-lived ticket authorizing SSE subscribe for ``topic``.

    Bound to topic (+ optional subject). Verified with channel secret
    (and ``previous_secrets`` on verify).
    """
    secret = getattr(config, "secret", None) if config is not None else None
    if not secret or len(str(secret)) < 16:
        raise ValueError("sign_push_ticket requires config.secret length >= 16")
    max_len = int(getattr(config, "push_topic_max_len", 128) or 128)
    t = validate_topic(topic, max_len=max_len)
    age = max_age
    if age is None:
        age = int(getattr(config, "push_ticket_max_age", 300) or 300)
    payload = {
        "v": 1,
        "topic": t,
        "iat": int(time.time()),
        "sub": sub,
        "extra": dict(extra or {}),
    }
    payload = {k: v for k, v in payload.items() if v is not None and v != {}}
    # max_age is enforced on verify; embed exp hint for clients
    payload["exp_hint"] = int(time.time()) + int(age)
    return _serializer(str(secret)).dumps(payload)


def verify_push_ticket(
    config: Any,
    ticket: str,
    topic: str,
    *,
    expected_sub: Optional[str] = None,
    max_age: Optional[int] = None,
) -> dict[str, Any]:
    """
    Verify ticket for this topic. Raises PushAuthError on failure.
    """
    secret = getattr(config, "secret", None) if config is not None else None
    if not secret:
        raise PushAuthError("push tickets not configured")
    max_len = int(getattr(config, "push_topic_max_len", 128) or 128)
    t = validate_topic(topic, max_len=max_len)
    age = max_age
    if age is None:
        age = int(getattr(config, "push_ticket_max_age", 300) or 300)

    serializers = [_serializer(str(secret))]
    for prev in getattr(config, "previous_secrets", ()) or ():
        if prev and len(str(prev)) >= 16 and prev != secret:
            serializers.append(_serializer(str(prev)))

    data = None
    last: Exception | None = None
    for ser in serializers:
        try:
            data = ser.loads(ticket, max_age=int(age))
            break
        except SignatureExpired as exc:
            last = exc
        except BadSignature as exc:
            last = exc
    if data is None:
        if isinstance(last, SignatureExpired):
            raise PushAuthError("push ticket expired")
        raise PushAuthError("push ticket invalid")

    if not isinstance(data, dict):
        raise PushAuthError("push ticket invalid")
    if data.get("topic") != t:
        raise PushAuthError("push ticket topic mismatch")
    if expected_sub is not None:
        if data.get("sub") != expected_sub:
            raise PushAuthError("push ticket subject mismatch")
    return data


def _token_ok(config: Any, token: Optional[str]) -> bool:
    expected = getattr(config, "push_token", None) if config is not None else None
    if not expected or not token:
        return False
    # constant-time compare
    import hmac

    return hmac.compare_digest(str(expected), str(token))


def authorize_push_subscribe(
    config: Any,
    topic: str,
    *,
    token: Optional[str] = None,
    ticket: Optional[str] = None,
    bearer: Optional[str] = None,
    expected_sub: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Decide whether a client may open SSE for ``topic``.

    Returns ``(True, "ok"|"public"|…)`` or ``(False, reason)``.

    Policy order
    ------------
    1. Validate topic shape
    2. If ``push_open`` — allow (explicit break-glass)
    3. If public prefix and ``push_allow_public`` — allow
    4. If ticket valid for topic — allow
    5. If shared push_token matches (token or bearer) — allow
    6. If not ``push_require_auth`` — allow (development default)
    7. Deny
    """
    ok_r, reason_r = _ticket_not_revoked(ticket)
    if not ok_r:
        _emit_push_deny(topic, reason_r)
        return False, reason_r
    try:
        max_len = int(getattr(config, "push_topic_max_len", 128) or 128) if config else 128
        t = validate_topic(topic, max_len=max_len)
    except PushAuthError as exc:
        _emit_push_deny(topic, str(exc) or "invalid topic")
        return False, str(exc) or "invalid topic"

    if config is None:
        # no config → open (mount without config); hosts should pass config in prod
        return True, "no_config"

    if getattr(config, "push_open", False):
        return True, "push_open"

    allow_public = getattr(config, "push_allow_public", True)
    is_public = bool(allow_public and topic_is_public(t, config))

    # Tenant prefix + topic policy (Wave integrity): apply before credential success
    ok_tp, why_tp = _tenant_and_policy(config, t, sub=expected_sub)
    if not ok_tp:
        # Public topics still go through policy; tenant only bites non-public inside helper
        _emit_push_deny(t, why_tp)
        return False, why_tp

    if is_public:
        return True, "public"

    # ticket first (scoped)
    if ticket:
        try:
            verify_push_ticket(config, ticket, t, expected_sub=expected_sub)
            return True, "ticket"
        except PushAuthError as exc:
            # fall through to token / deny — but remember failure if require auth
            ticket_err = str(exc)
        else:
            ticket_err = None
    else:
        ticket_err = None

    cred = token or bearer
    if _token_ok(config, cred):
        return True, "push_token"

    # If a shared push_token is configured, non-public topics must present it
    # (or a valid ticket above). Wrong/missing token → deny even in development.
    configured_token = getattr(config, "push_token", None)
    if configured_token:
        if ticket_err:
            _emit_push_deny(t, ticket_err)
            return False, ticket_err
        if cred:
            _emit_push_deny(t, "push token invalid")
            return False, "push token invalid"
        _emit_push_deny(t, "push token required")
        return False, "push token required"

    require = getattr(config, "push_require_auth", None)
    if require is None:
        # default: production fail-closed, development open
        require = getattr(config, "environment", "production") == "production"

    if not require:
        return True, "auth_not_required"

    if ticket_err:
        return False, ticket_err
    if cred:
        return False, "push token invalid"
    _emit_push_deny(t, "push authorization required")
    return False, "push authorization required"


def extract_push_credentials(
    headers: Optional[Mapping[str, str]] = None,
    query: Optional[Mapping[str, str]] = None,
) -> dict[str, Optional[str]]:
    """
    Pull token/ticket/bearer from HTTP headers and query (case-insensitive headers).
    """
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    query = {str(k): str(v) for k, v in (query or {}).items()}
    auth = headers.get("authorization") or ""
    bearer = None
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip() or None
    return {
        "token": query.get("token") or headers.get("x-channel-push-token"),
        "ticket": query.get("ticket") or headers.get("x-channel-push-ticket"),
        "bearer": bearer,
    }
