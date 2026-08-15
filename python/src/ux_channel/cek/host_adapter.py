"""CapService façade → cek_host.Host (ADAPT / REQUIRE).

Invariant 1: present_cap_must_verify — bogus cap fails closed.
Invariant 2: once=true ⇒ same jti replay fails closed.
Invariant 3: sealed-args — client cannot override server-sealed fields.
Invariant 5: mint(action, args) → verify(token, action, args) succeeds.
Invariant 6: different action or args → verify fails.
Invariant 7: oracle hash_args({\\"sku\\":\\"abc-123\\",\\"qty\\":2}) == 96e4f83e3793b646323a67f314b51044

Channel product CapService (itsdangerous) stays the off-path machine.
This wrapper is installed only when ChannelConfig.cek is adapt|require.
Token format on the require path is cek-host (hex+HMAC). Classic clients
on cek=off are unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from ux_channel.cek.config import parse_cek, require_cek_installed
from ux_channel.protocol.capability import CapError
from ux_channel.protocol.capability import CapService as ChannelCapService

log = logging.getLogger("ux_channel.cek.host_adapter")

# Dual-language oracle (TESTING.md / SPEC/INVARIANTS).
ORACLE_ARGS = {"sku": "abc-123", "qty": 2}
ORACLE_HASH = "96e4f83e3793b646323a67f314b51044"


class CekHostCapService:
    """CapService-shaped façade over ``cek_host.CapService``.

    Matches Channel's always-seal semantics (``seal_args=True``).
    Exposes ``mint`` / ``verify`` / ``hash_args`` so ActionRegistry can swap
    ``_caps`` without a second name.
    """

    def __init__(
        self,
        secret: str,
        *,
        max_age: int = 3600,
        previous_secrets: Optional[Sequence[str]] = None,
        nonce_store: Any = None,
    ) -> None:
        from cek_host.cap import CapService as HostCaps

        raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        self._host = HostCaps(secret=raw, ttl_s=int(max_age or 3600))
        self._channel_hash = ChannelCapService.hash_args
        self.max_age = int(max_age or 3600)
        self.nonce_store = nonce_store
        self.previous_secrets = tuple(previous_secrets or ())
        self.name = "cek_host.CapService"

    def hash_args(self, args: Mapping[str, Any] | None = None) -> str:
        # Same oracle as Channel / Rust. Prefer Channel's helper so default=str
        # matches existing vectors; cek-host args_hash agrees on the oracle.
        return ChannelCapService.hash_args(args)

    def mint(
        self,
        action: str,
        args: Mapping[str, Any] | None = None,
        *,
        extra: Mapping[str, Any] | None = None,
        sub: str | None = None,
        scopes: Sequence[str] | None = None,
        jti: str | None = None,
        once: bool = False,
        **_kw: Any,
    ) -> str:
        sealed = dict(args or {})
        if extra:
            sealed.update(dict(extra))
        try:
            return self._host.mint(
                action,
                once=bool(once),
                args=sealed,
                seal_args=True,
                scopes=list(scopes) if scopes else None,
                subject=sub,
                jti=jti,
            )
        except Exception as exc:
            raise CapError(str(exc)) from exc

    def verify(
        self,
        token: str,
        action: str,
        args: Mapping[str, Any] | None = None,
        *,
        max_age: int | None = None,
        expected_sub: str | None = None,
        required_scopes: Sequence[str] | None = None,
        consume_once: bool = True,
        nonce_store: Any = None,
        **_kw: Any,
    ) -> dict[str, Any]:
        # present_cap_must_verify — empty/bogus token fails closed.
        if not token:
            raise CapError("missing capability")
        try:
            claims = self._host.verify(
                token,
                action,
                dict(args or {}),
                consume_once=consume_once,
                subject=expected_sub,
            )
        except Exception as exc:
            # Map cek-host CapError → Channel CapError (same name, one machine
            # on this path).
            raise CapError(str(exc)) from exc
        if required_scopes:
            have = set(claims.get("scopes") or [])
            missing = [s for s in required_scopes if s not in have]
            if missing:
                raise CapError("capability missing required scopes")
        # Durable nonce store (Redis / MemoryNonceStore) still fail-closes
        # when Channel attached one — cek-host's in-memory jti is the
        # in-process half; multi-worker uses the Channel store if present.
        store = nonce_store if nonce_store is not None else self.nonce_store
        if claims.get("once") and consume_once and store is not None:
            jti = str(claims.get("jti") or "")
            if not jti:
                raise CapError("empty jti")
            ttl = int(max_age or self.max_age or 3600)
            try:
                ok = store.use_once(jti, ttl_s=ttl)
            except Exception as exc:
                raise CapError("nonce store refused") from exc
            if ok is False:
                raise CapError("once cap already used")
        return claims


def apply_host_adapter(registry: Any, config: Any) -> str:
    """Swap ``registry._caps`` when cek is adapt|require.

    off     — no-op, zero imports.
    adapt   — install adapter; Channel product still works. Used for A-vs-B.
    require — adapter **is** the Cap machine. Fail closed if extra missing.

    Returns the mode that was applied.
    """
    mode = parse_cek(getattr(config, "cek", "off") if config is not None else "off")
    if mode == "off":
        return mode
    require_cek_installed(mode)
    secret = getattr(config, "secret", None) or getattr(registry, "_secret", None)
    if not secret:
        # ActionRegistry stores secret on the CapService.
        caps = getattr(registry, "_caps", None)
        secret = getattr(caps, "secret", None) or getattr(caps, "_secret", None)
    if not secret:
        raise RuntimeError("cek adapter needs a secret on ChannelConfig / registry")
    adapted = CekHostCapService(
        str(secret),
        max_age=int(getattr(config, "max_cap_age", 3600) or 3600),
        previous_secrets=tuple(getattr(config, "previous_secrets", ()) or ()),
        nonce_store=getattr(registry, "_nonce_store", None),
    )
    if mode == "require":
        registry._caps = adapted
        log.info("cek=require: CapService → cek_host (present_cap_must_verify)")
    else:
        # adapt: expose side-by-side for parity tests; Channel stays authority.
        registry._cek_caps = adapted
        log.info("cek=adapt: adapter live; Channel CapService remains authority")
    return mode
