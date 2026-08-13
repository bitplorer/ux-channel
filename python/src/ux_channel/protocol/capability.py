"""
Cap tokens — HMAC authority (Rust-parity: CapService, mint, verify, CapError) for browser→server Intents.

First principles
----------------
Anything the browser can POST can be forged. A **capability** (cap) is a
server-minted, HMAC-signed token that binds:

- action name
- args hash (trusted / sealed args)
- optional subject (principal)
- optional once-jti (single use with nonce store)
- expiry

``ch.control(action, trust_sku=...)`` mints a cap (Rust: CapService::mint); the client sends it back
on Intent; the registry verifies before the handler runs.

Trust vs form
-------------
- **trust_*** args are sealed — client cannot change them without invalidating the cap.
- **form** fields (progressive enhance) fill missing args and are not in the hash by default.

Never put secrets in args. Prefer ids + server-side reload of truth.

once / jti
----------
``mint(..., once=True)`` binds a unique ``jti``. ``verify`` consumes that jti
atomically **before** the caller runs side effects. No nonce store → refuse
(fail closed). Replay of the same jti → ``CapError``. Pass
``consume_once=False`` only for inspection (attenuation, tests).

See: docs/SECURITY_AUDIT.md, docs/DESIGN.md.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Mapping, Optional, Sequence

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ux_channel.protocol.errors import ChannelError


class CapError(ChannelError):
    """Invalid, expired, or mismatched capability."""


class CapService:
    """
    HMAC capability tokens — **Rust-parity name** (``CapService`` / ``mint`` / ``verify``).

    HMAC tokens bound to action + args hash (+ optional principal).

    Parameters
    ----------
    secret:
        Active signing key (min 16 chars).
    previous_secrets:
        Older keys still accepted on verify (rotation window). Never used to sign.
    nonce_store:
        Optional ``use_once(key, ttl_s=)`` store. Required to verify ``once`` caps
        when ``consume_once=True`` (the default).
    """

    def __init__(
        self,
        secret: str,
        *,
        max_age: int = 3600,
        salt: str = "ux-channel-cap",
        previous_secrets: Optional[Sequence[str]] = None,
        nonce_store: Any = None,
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
        self.nonce_store = nonce_store

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
        if once and not jti:
            jti = uuid.uuid4().hex
        payload = {
            "action": action,
            "args_hash": self.hash_args(args or {}),
            "extra": dict(extra or {}),
            "iat": int(time.time()),
            "sub": sub,
            "scopes": list(scopes) if scopes else None,
            "jti": jti,
            "once": bool(once) or None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return self._ser.dumps(payload)

    def verify(
        self,
        token: str,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        max_age: Optional[int] = None,
        expected_sub: Optional[str] = None,
        required_scopes: Optional[Sequence[str]] = None,
        consume_once: bool = True,
        nonce_store: Any = None,
    ) -> dict[str, Any]:
        """
        Unsign + check action/args/principal/scopes, then consume once/jti.

        ``consume_once=True`` (default) is the authorization path: atomic
        consume before side effects. Missing store or missing jti on an
        ``once`` token is a hard refuse. Pass ``consume_once=False`` to
        inspect claims without burning the nonce.
        """
        if not token:
            raise CapError("capability token required")
        age = max_age if max_age is not None else self._max_age
        data = None
        last_exc: Exception | None = None
        for ser in (self._ser, *self._previous):
            try:
                data = ser.loads(token, max_age=age)
                break
            except SignatureExpired as exc:
                raise CapError("capability expired — re-render control via ch.control") from exc
            except BadSignature as exc:
                last_exc = exc
                continue
        if data is None:
            raise CapError("invalid capability — use ch.control, do not hand-build caps") from last_exc

        if data.get("action") != action:
            raise CapError("capability action mismatch")
        expected = self.hash_args(args or {})
        if data.get("args_hash") != expected:
            raise CapError("capability args mismatch")
        if expected_sub is not None:
            if data.get("sub") != expected_sub:
                raise CapError("capability principal mismatch")
        if required_scopes:
            have = set(data.get("scopes") or [])
            if "*" not in have and not set(required_scopes).issubset(have):
                raise CapError("capability missing scopes")

        if data.get("once") and consume_once:
            store = nonce_store if nonce_store is not None else self.nonce_store
            jti = data.get("jti")
            if not jti or not str(jti).strip():
                raise CapError("once capability missing jti")
            if store is None:
                raise CapError(
                    "once capability requires nonce_store "
                    "(configure MemoryNonceStore or RedisNonceStore)"
                )
            if not store.use_once(f"cap:{jti}", ttl_s=float(self._max_age)):
                raise CapError("capability replay (nonce)")
        return data

    @staticmethod
    def hash_args(args: Mapping[str, Any] | None = None) -> str:
        """Rust-parity: ``CapService::hash_args`` — sorted compact JSON, sha256 hex[:32]."""
        payload = args or {}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
