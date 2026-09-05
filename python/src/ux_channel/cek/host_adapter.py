"""CapService façade → cek-runtime Host (cut #2).

off     — this module is not imported.
adapt   — Host on registry._cek_caps; Channel CapService stays authority.
require — registry._caps is this façade. One Cap machine.

The Cap machine is **cek-runtime Host** (ADR 0008): ``RustHostKernel`` /
``cek host-json`` when CEK_BIN is the runtime binary, else the documented
port Host (``cek_host.Host``). Tokens stay port-Host hex+HMAC so Channel
sealed-args / once / oracle remain stateful (host-json is a fresh Host
per call). ``cek_surface`` is compose only — not a kernel.

Channel ops stay classic IR 0.1. S pairs only go through cek.project.
EffectGraph is L7 pre-project after Cap (see ``after_cek_cut2``).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from ux_channel.cek.config import parse_cek, require_cek_installed
from ux_channel.cek.encode import (
    flow_id_to_trace,
    hello_to_manifest,
    hello_to_profile,
    intent_trace,
)
from ux_channel.cek.runtime_host import (
    KERNEL_SSOT,
    KERNEL_SSOT_ADR,
    bind_runtime_host,
)
from ux_channel.protocol.capability import CapError
from ux_channel.protocol.capability import CapService as ChannelCapService
from ux_channel.protocol.types import ErrorObject, Result

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
    """CapService-shaped façade over cek-runtime Host (port and/or rust_wrap).

    Always seals args. Tokens are the documented port Host (hex+HMAC), not
    itsdangerous. ``kernel_ssot`` is always ``cek-runtime``.
    """

    def __init__(
        self,
        secret: str,
        *,
        max_age: int = 3600,
        previous_secrets: Optional[Sequence[str]] = None,
        nonce_store: Any = None,
    ) -> None:
        bind = bind_runtime_host(
            secret,
            max_age=int(max_age or 3600),
            previous_secrets=previous_secrets,
        )
        self._host = bind.host
        self.runtime_kernel = bind.runtime_kernel
        self.backend = bind.backend
        self.kernel_ssot = bind.kernel_ssot
        self.kernel_ssot_adr = bind.kernel_ssot_adr
        self.bin_path = bind.bin_path
        self.max_age = int(max_age or 3600)
        self.nonce_store = nonce_store
        self.previous_secrets = tuple(previous_secrets or ())
        self.name = "cek-runtime.Host"

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


def after_cek_cut2(intent: Any, result: Any) -> Any:
    """Encoding + L7 EffectGraph gate. Registered on adapt|require.

    * ``flow_id`` → ``meta.trace`` (correlation only)
    * hello → Profile / Manifest on result.meta (handshake; not Cap)
    * ``_graph`` without a present Cap is refused (EffectGraph is L7 after Cap)
    """
    if not isinstance(result, Result):
        return result
    cap = getattr(intent, "cap", None)
    if result.meta and "_graph" in result.meta and not cap:
        result.meta.pop("_graph", None)
        result.ops = []
        result.ok = False
        result.error = ErrorObject(
            code="forbidden",
            message="EffectGraph is L7 pre-project after Cap only",
        )
        return result

    meta_in = getattr(intent, "meta", None) or {}
    args = getattr(intent, "args", None) or {}
    if not isinstance(meta_in, Mapping):
        meta_in = {}
    if not isinstance(args, Mapping):
        args = {}

    fid = args.get("flow_id") or meta_in.get("flow_id")
    if fid:
        result.meta.setdefault("flow_id", str(fid))
        tr = flow_id_to_trace(fid)
        if tr:
            result.meta.setdefault("trace", tr)
    else:
        tr = intent_trace(meta=meta_in, args=args)
        if tr:
            result.meta.setdefault("trace", tr)

    hello = meta_in.get("hello") if isinstance(meta_in, Mapping) else None
    if isinstance(hello, dict):
        result.meta.setdefault("profile", hello_to_profile(hello))
        result.meta.setdefault("manifest", hello_to_manifest(hello))
    return result


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
        log.info(
            "cek=require: CapService → %s Host (%s, ADR %s)",
            KERNEL_SSOT,
            adapted.backend,
            KERNEL_SSOT_ADR,
        )
    else:
        registry._cek_caps = adapted
        log.info(
            "cek=adapt: cek-runtime Host wrap live (%s); Channel CapService remains authority",
            adapted.backend,
        )
    after = getattr(registry, "after", None)
    if callable(after):
        after(after_cek_cut2)
    return mode
