"""
Capability tokens — HMAC authority for browser→server Intents.

First principles
----------------
Anything the browser can POST can be forged. A **capability** (cap) is a
server-minted, HMAC-signed token that binds:

- action name
- args hash (trusted / sealed args)
- optional subject (principal)
- optional once-jti (single use with nonce store)
- expiry

``ch.control(action, trust_sku=...)`` signs a cap; the client sends it back
on Intent; the registry verifies before the handler runs.

Trust vs form
-------------
- **trust_*** args are sealed — client cannot change them without invalidating the cap.
- **form** fields (progressive enhance) fill missing args and are not in the hash by default.

Never put secrets in args. Prefer ids + server-side reload of truth.

See: docs/SECURITY_AUDIT.md, docs/DESIGN.md.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Mapping, Optional, Sequence

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ux_channel.errors import ChannelError


class CapabilityError(ChannelError):
    """Invalid, expired, or mismatched capability."""


class CapabilityService:
    """
    HMAC capability tokens bound to action + args hash (+ optional principal).

    Parameters
    ----------
    secret:
        Active signing key (min 16 chars).
    previous_secrets:
        Older keys still accepted on verify (rotation window). Never used to sign.
    """

    def __init__(
        self,
        secret: str,
        *,
        max_age: int = 3600,
        salt: str = "ux-channel-cap",
        previous_secrets: Optional[Sequence[str]] = None,
    ):
        if not secret or not isinstance(secret, str):
            raise ValueError("capability secret must be non-empty")
        if len(secret) < 16:
            raise ValueError(
                "capability secret must be at least 16 characters "
                "(use secrets.token_urlsafe(32) in production)"
            )
        self._max_age = max_age
        self._salt = salt
        self._ser = URLSafeTimedSerializer(secret_key=secret, salt=salt)
        self._previous: list[URLSafeTimedSerializer] = []
        for prev in previous_secrets or ():
            if not prev or len(prev) < 16:
                continue
            if prev == secret:
                continue
            self._previous.append(URLSafeTimedSerializer(secret_key=prev, salt=salt))

    def sign(
        # Prefer mint() in new speech — identical implementation.
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        sub: Optional[str] = None,
        scopes: Optional[Sequence[str]] = None,
        jti: Optional[str] = None,
        once: bool = False,
    ) -> str:
        if once and not jti:
            jti = uuid.uuid4().hex
        payload = {
            "action": action,
            "args_hash": self._hash_args(args or {}),
            "extra": dict(extra or {}),
            "iat": int(time.time()),
            "sub": sub,
            "scopes": list(scopes) if scopes else None,
            "jti": jti,
            "once": bool(once) or None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return self._ser.dumps(payload)


    def mint(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        sub: Optional[str] = None,
        scopes: Optional[Sequence[str]] = None,
        jti: Optional[str] = None,
        once: bool = False,
    ) -> str:
        """Create a capability token — **same function as** ``sign``.

        Naming intent
        -------------
        * **mint** — product / Rust speech ("issue a cap")
        * **sign** — historical Python/itsdangerous speech

        Prefer **mint** in new code and docs so Python and Rust say the same verb.
        """
        return self.sign(
            action, args, extra=extra, sub=sub, scopes=scopes, jti=jti, once=once
        )

    def verify(
        self,
        token: str,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        max_age: Optional[int] = None,
        expected_sub: Optional[str] = None,
        required_scopes: Optional[Sequence[str]] = None,
    ) -> dict[str, Any]:
        age = max_age if max_age is not None else self._max_age
        data = None
        last_exc: Exception | None = None
        for ser in (self._ser, *self._previous):
            try:
                data = ser.loads(token, max_age=age)
                break
            except SignatureExpired as exc:
                raise CapabilityError("capability expired — re-render control via ch.control") from exc
            except BadSignature as exc:
                last_exc = exc
                continue
        if data is None:
            raise CapabilityError("invalid capability — use ch.control, do not hand-build caps") from last_exc

        if data.get("action") != action:
            raise CapabilityError("capability action mismatch")
        expected = self._hash_args(args or {})
        if data.get("args_hash") != expected:
            raise CapabilityError("capability args mismatch")
        if expected_sub is not None:
            if data.get("sub") != expected_sub:
                raise CapabilityError("capability principal mismatch")
        if required_scopes:
            have = set(data.get("scopes") or [])
            if "*" not in have and not set(required_scopes).issubset(have):
                raise CapabilityError("capability missing scopes")
        return data

    @staticmethod
    def _hash_args(args: Mapping[str, Any]) -> str:
        # Canonical form is LAW (SPEC + conformance oracle + Rust CapService):
        # sorted keys, compact separators, default=str. Do NOT use unordered
        # JSON engines here — key order would break interop.
        raw = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
