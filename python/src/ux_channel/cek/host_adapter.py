"""CapService façade → cek_host.Host (0.1.3+).

off     — this module is not imported.
adapt   — Host on registry._cek_caps; Channel CapService stays authority.
require — registry._caps is this façade. One Cap machine.

Channel ops stay classic IR 0.1. S pairs only go through cek.project.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from ux_channel.cek.config import parse_cek, require_cek_installed
from ux_channel.protocol.capability import CapError
from ux_channel.protocol.capability import CapService as ChannelCapService

log = logging.getLogger("ux_channel.cek.host_adapter")

ORACLE_ARGS = {"sku": "abc-123", "qty": 2}
ORACLE_HASH = "96e4f83e3793b646323a67f314b51044"
MIN_CEK = (0, 1, 3)


def _cek_version_tuple() -> tuple[int, int, int]:
    import cek_host

    raw = getattr(cek_host, "__version__", "0.0.0")
    parts = []
    for bit in str(raw).split(".")[:3]:
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def require_cek_min() -> None:
    ver = _cek_version_tuple()
    if ver < MIN_CEK:
        raise RuntimeError(
            f"ux-channel[cek] needs cek-host>=0.1.3 (got {ver[0]}.{ver[1]}.{ver[2]}). "
            "pip install -U 'cek-host>=0.1.3' 'cek-surface>=0.1.3'"
        )


class CekHostCapService:
    """CapService-shaped façade over ``cek_host.Host``.

    Always seals args. Tokens are cek-host (hex+HMAC), not itsdangerous.
    """

    def __init__(
        self,
        secret: str,
        *,
        max_age: int = 3600,
        previous_secrets: Optional[Sequence[str]] = None,
        nonce_store: Any = None,
    ) -> None:
        from cek_host import Host, MemoryOnceBackend

        raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        self._host = Host(
            secret=raw,
            ttl_s=int(max_age or 3600),
            once=MemoryOnceBackend(),
            require_cap=True,
        )
        self.max_age = int(max_age or 3600)
        self.nonce_store = nonce_store
        self.previous_secrets = tuple(previous_secrets or ())
        self.name = "cek_host.Host"

    @property
    def host(self) -> Any:
        return self._host

    def hash_args(self, args: Mapping[str, Any] | None = None) -> str:
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
        if not token:
            raise CapError("missing capability")
        try:
            claims = self._host.caps.verify(
                token,
                action,
                dict(args or {}),
                consume_once=consume_once,
                subject=expected_sub,
            )
        except Exception as exc:
            raise CapError(str(exc)) from exc
        if required_scopes:
            have = set(claims.get("scopes") or [])
            missing = [s for s in required_scopes if s not in have]
            if missing:
                raise CapError("capability missing required scopes")
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

    async def async_verify(
        self,
        token: str,
        action: str,
        args: Mapping[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        """Same law as verify. Does not occupy the event loop."""
        import asyncio

        return await asyncio.to_thread(self.verify, token, action, args, **kw)


def apply_host_adapter(registry: Any, config: Any) -> str:
    """Swap ``registry._caps`` when cek is adapt|require."""
    mode = parse_cek(getattr(config, "cek", "off") if config is not None else "off")
    if mode == "off":
        return mode
    require_cek_installed(mode)
    require_cek_min()
    secret = getattr(config, "secret", None) or getattr(registry, "_secret", None)
    if not secret:
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
        log.info("cek=require: CapService → cek_host.Host 0.1.3+")
    else:
        registry._cek_caps = adapted
        log.info("cek=adapt: Host adapter live; Channel CapService remains authority")
    return mode
