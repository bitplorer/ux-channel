"""ActionRegistry — Intent → handler → Result.

    Intent → cap + hooks → handler (sync or async) → Result

``dispatch`` refuses ``async def``. ``async_dispatch`` runs both.
``dispatch_async`` is an alias of ``async_dispatch``.
"""


from __future__ import annotations

import asyncio
import contextvars
import inspect
import logging
import threading
import time
import weakref
from typing import Any, Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from ux_channel.protocol.capability import CapError, CapService
from ux_channel.host.context import (
    ActionContext,
    AuthResolver,
    IDENTITY_KEYS,
    Principal,
    VerifiedContext,
    cap_subject,
)
from ux_channel.protocol.navigate_markers import Navigate
from ux_channel.protocol.errors import ActionError
from ux_channel.host.hooks import AfterHook, BeforeHook, HookList

def _call_encode_result(*args, **kwargs):
    from ux_channel.protocol.encode import encode_result as _enc

    return _enc(*args, **kwargs)



def _trace_api():
    """Lazy L5 tooling — keep host registry free of eager devtools import."""
    from ux_channel.devtools import trace as _trace

    return _trace

from ux_channel.host.idempotency import IdempotencyCapacityError, IdempotencyStore

try:
    from redis.exceptions import RedisError as _RedisStoreError
except ImportError:  # pragma: no cover - redis extra is optional

    class _RedisStoreError(Exception):
        """Stand-in when the redis package is not installed."""
from ux_channel.security.limits import (
    DEFAULT_MAX_HTML_BYTES,
    DEFAULT_MAX_OPS,
    DEFAULT_MAX_RESULT_BYTES,
    LimitExceeded,
    enforce_result_limits,
)
from ux_channel.host.nonce import NonceStore
from ux_channel.security.security import filter_outbound_ops, validate_action_name


class AsyncDispatchRequired(TypeError):
    """Raised when sync dispatch meets an async handler or hook."""


class AuthResolverFailed(RuntimeError):
    """auth_resolver raised — fail closed (not anonymous)."""


def _sec(kind: str, **kw) -> None:
    try:
        from ux_channel.security.security_events import emit_security
        emit_security(kind, **kw)
    except Exception:
        logger.debug("security_events emit failed kind=%s", kind, exc_info=True)

from ux_channel.protocol.json_codec import JsonLimitError, check_json_limits
from ux_channel.protocol.types import Intent, Result

if TYPE_CHECKING:
    from ux_channel.host.config import ChannelConfig

ActionHandler = Callable[..., Any]
_principal_override: contextvars.ContextVar = contextvars.ContextVar("uid_principal", default=None)
logger = logging.getLogger("ux_channel.host.registry")
_request_var: contextvars.ContextVar[Any] = contextvars.ContextVar("ux_channel_request", default=None)


def _bound_origin_host(request: Any) -> str | None:
    """``Host`` header of the request bound for this dispatch, if any."""
    headers = getattr(request, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    host = getter("host")
    if host is None or host == "":
        return None
    return str(host)


class SyncLockTimeout(TimeoutError):
    """Another thread still holds this action owner's sync lock."""

    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"sync handler lock timed out after {timeout_s:g}s")
        self.timeout_s = timeout_s


def _sync_owner(handler: ActionHandler) -> Any:
    """Component instance for a bound method, otherwise the function itself."""
    component = getattr(handler, "__self__", None)
    return component if component is not None else handler


class ActionRegistry:
    """
    Named action table + capability service + hook pipeline.

    Parameters (via ``__init__`` / ``from_config``)
    ----------------------------------------------
    secret / config:
        HMAC material for capabilities.
    require_cap:
        Production True — reject missing/invalid caps.
    nonce_store / idempotency_store:
        Replay protection for once-caps (classic ``CapService`` / ``cek=off``)
        and client idempotency keys. On ``cek=require``, Host consumes once
        — Channel ``nonce_store`` is not re-consumed (cut #5A).
    auth_resolver:
        Optional request → Principal.
    action_timeout_s:
        Wall-clock limit per action (0 = none).
    sync_lock_timeout_s:
        How long a cross-thread re-dispatch waits for the same action
        owner's sync lock. Default 30s, or ``config.sync_lock_timeout_s``
        when that attribute is set. The same thread may re-enter. Different
        owners do not share a lock. On timeout the Result code is
        ``timeout``. The waiter can still block until that deadline.

    Public methods
    --------------
    action / register:
        Register handlers; pass ``idempotent=True`` for safe auto-retry.
    dispatch / async_dispatch:
        Run one Intent to a Result.
    sign:
        Mint capability tokens for ``ch.control``.
    is_idempotent / action_meta:
        Query registration metadata (batch retry, diagnostics).
    """

    def __init__(
        self,
        secret: str,
        *,
        renderer: Any = None,
        require_cap: bool = True,
        max_cap_age: int = 3600,
        max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
        max_ops: int = DEFAULT_MAX_OPS,
        max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES,
        verify_form_in_cap: bool = False,
        expose_internal_errors: bool = False,
        action_timeout_s: float = 0.0,
        sync_lock_timeout_s: Optional[float] = None,
        config: Optional["ChannelConfig"] = None,
        nonce_store: Optional[NonceStore] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
        auth_resolver: Optional[AuthResolver] = None,
        require_principal: bool = False,
        previous_secrets: Optional[Sequence[str]] = None,
    ):
        self._actions: dict[str, ActionHandler] = {}
        self._action_meta: dict[str, dict[str, Any]] = {}
        self._caps = CapService(
            secret,
            max_age=max_cap_age,
            previous_secrets=previous_secrets,
            nonce_store=nonce_store,
        )
        if renderer is None:
            from ux_channel.render.renderers import ChainRenderer, StringRenderer

            renderer = ChainRenderer(StringRenderer())
        self._renderer = renderer
        self.require_cap = require_cap
        self.max_html_bytes = max_html_bytes
        self.max_ops = max_ops
        self.max_result_bytes = max_result_bytes
        self.verify_form_in_cap = verify_form_in_cap
        self.expose_internal_errors = expose_internal_errors
        self.action_timeout_s = float(action_timeout_s or 0.0)
        self.config = config
        self.hooks = HookList()
        self._nonce_store = nonce_store
        self.idempotency_store = idempotency_store
        self.auth_resolver = auth_resolver
        self.require_principal = require_principal
        configured_lock = (
            getattr(config, "sync_lock_timeout_s", None) if config is not None else None
        )
        chosen_lock = (
            sync_lock_timeout_s if sync_lock_timeout_s is not None else configured_lock
        )
        # Per-owner sync lock. Default 30s. Cross-thread re-dispatch to the
        # same owner waits only this long, then SyncLockTimeout.
        self.sync_lock_timeout_s = float(30.0 if chosen_lock is None else chosen_lock)
        self._owner_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._owner_locks_guard = threading.Lock()
        # optional request stashed by host for auth_resolver

    def _cek_require_owns_once(self) -> bool:
        """True when registry._caps is the cek-runtime Host façade (cut #5A)."""
        return type(self._caps).__name__ == "CekHostCapService"

    @property
    def nonce_store(self) -> Optional[NonceStore]:
        return self._nonce_store

    @nonce_store.setter
    def nonce_store(self, store: Optional[NonceStore]) -> None:
        self._nonce_store = store
        # Classic CapService only. require Host owns once — do not wire.
        if not self._cek_require_owns_once():
            self._caps.nonce_store = store

    @property
    def once_jti_enforced(self) -> bool:
        """Host consumes once on require; Channel nonce_store on classic off."""
        if self._cek_require_owns_once():
            return True
        return self._nonce_store is not None

    @classmethod
    def from_config(
        cls,
        config: "ChannelConfig",
        *,
        renderer: Any = None,
        install_defaults: bool = True,
        nonce_store: Optional[NonceStore] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
        auth_resolver: Optional[AuthResolver] = None,
    ) -> "ActionRegistry":
        config.validate()
        reg = cls(
            config.secret,
            renderer=renderer,
            require_cap=config.require_cap,
            max_cap_age=config.max_cap_age,
            max_html_bytes=config.max_html_bytes,
            max_ops=config.max_ops,
            max_result_bytes=config.max_result_bytes,
            expose_internal_errors=config.expose_internal_errors,
            action_timeout_s=config.action_timeout_s,
            config=config,
            nonce_store=nonce_store,
            idempotency_store=idempotency_store,
            auth_resolver=auth_resolver,
            require_principal=bool(getattr(config, "require_principal", False)),
            previous_secrets=tuple(getattr(config, "previous_secrets", ()) or ()),
        )
        if install_defaults:
            from ux_channel.devtools.observability import observability_after_hook
            from ux_channel.security.ratelimit import MemoryRateLimiter, rate_limit_hook
            from ux_channel.devtools.trace import TraceConfig

            # Wave 5: policy engine (no-op until rules registered)
            def _policy_before(intent, args=None, principal=None, **kw):
                from ux_channel.security.policy import get_policy
                eng = get_policy()
                if eng is None:
                    return None
                ok, reason = eng.check_action(intent, principal)
                if not ok:
                    from ux_channel.protocol.types import Result
                    from ux_channel.security.security_events import emit_security
                    emit_security(
                        "policy_deny",
                        action=getattr(intent, "action", ""),
                        reason=reason,
                    )
                    return Result.failure("forbidden", reason or "policy denied")
                return None
            reg.before(_policy_before)

            if getattr(config, "trace_enabled", False):
                _trace_api().get_tracer().configure(
                    TraceConfig(
                        enabled=True,
                        retain=int(getattr(config, "trace_retain", 500) or 500),
                        capture_payloads=bool(
                            getattr(config, "trace_capture_payloads", True)
                        ),
                        sample_rate=float(getattr(config, "trace_sample_rate", 1.0) or 1.0),
                    )
                )
            if config.rate_limit_per_minute > 0:
                limiter = MemoryRateLimiter(
                    rate_per_minute=config.rate_limit_per_minute,
                    burst=float(config.rate_limit_burst),
                )
                reg.before(rate_limit_hook(limiter))  # type: ignore[arg-type]
            if config.log_actions:
                reg.after(
                    observability_after_hook(  # type: ignore[arg-type]
                        log_slow_ms=config.log_slow_ms,
                        log_all=config.environment == "development",
                    )
                )
        # One Cap machine: from_config honors config.cek (compose / lower-level
        # path). create_channel may call apply_host_adapter again — idempotent.
        from ux_channel.cek.config import parse_cek

        if parse_cek(getattr(config, "cek", "require")) != "off":
            from ux_channel.cek.host_adapter import apply_host_adapter

            apply_host_adapter(reg, config)
        return reg

    def action(
        self,
        name: str | None = None,
        *,
        idempotent: bool = False,
    ) -> Callable[[ActionHandler], ActionHandler]:
        """
        Register an action.

        ``idempotent=True`` means the handler is safe to auto-retry (batch /
        client). Mutations that are not safe under replay must leave this False
        (default). Once-caps remain single-use regardless.
        """

        def decorator(fn: ActionHandler) -> ActionHandler:
            key = name if name is not None else fn.__name__
            self.register(key, fn, idempotent=idempotent)
            return fn

        return decorator

    def register(
        self,
        name: str,
        fn: ActionHandler,
        *,
        idempotent: bool = False,
        **extra_meta: Any,
    ) -> None:
        name = validate_action_name(name)
        if name in self._actions:
            raise ValueError(f"action already registered: {name}")
        self._actions[name] = fn
        meta = {"idempotent": bool(idempotent) or bool(getattr(fn, "idempotent", False))}
        for k, v in extra_meta.items():
            if v is not None:
                meta[k] = v
        self._action_meta[name] = meta
        try:
            setattr(fn, "idempotent", meta["idempotent"])
        except (AttributeError, TypeError):
            pass

    def replace(
        self,
        name: str,
        fn: ActionHandler,
        *,
        idempotent: bool | None = None,
        **extra_meta: Any,
    ) -> None:
        name = validate_action_name(name)
        prev = dict(self._action_meta.get(name, {}))
        self._actions[name] = fn
        flag = (
            bool(idempotent)
            if idempotent is not None
            else bool(prev.get("idempotent") or getattr(fn, "idempotent", False))
        )
        prev["idempotent"] = flag
        for k, v in extra_meta.items():
            if v is not None:
                prev[k] = v
        self._action_meta[name] = prev
        try:
            setattr(fn, "idempotent", flag)
        except (AttributeError, TypeError):
            pass

    def update_action_meta(self, name: str, **extra: Any) -> None:
        """Merge optional AX/region metadata onto an existing action."""
        name = validate_action_name(name)
        cur = dict(self._action_meta.get(name, {}))
        for k, v in extra.items():
            if v is not None:
                cur[k] = v
        self._action_meta[name] = cur

    def unregister(self, name: str) -> None:
        self._actions.pop(name, None)
        self._action_meta.pop(name, None)

    def is_idempotent(self, name: str) -> bool:
        """True if action was registered with idempotent=True."""
        return bool(self._action_meta.get(name, {}).get("idempotent"))

    def action_meta(self, name: str) -> dict[str, Any]:
        return dict(self._action_meta.get(name) or {})

    def names(self) -> list[str]:
        return sorted(self._actions)

    def get(self, name: str) -> Optional[ActionHandler]:
        return self._actions.get(name)

    def before(self, fn: BeforeHook) -> BeforeHook:
        return self.hooks.add_before(fn)

    def after(self, fn: AfterHook) -> AfterHook:
        return self.hooks.add_after(fn)

    def mint(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        **extra: Any,
    ) -> str:
        """Sign capability; pass sub=, scopes=, once= as kwargs into CapService."""
        action = validate_action_name(action)
        if action not in self._actions:
            # Cap can be minted before handler registration in some boot orders;
            # still warn — unsigned-name typos ship dead controls to the browser.
            logger.warning(
                "sign_unknown_action action=%s (no handler registered yet)",
                action,
            )
        sub = extra.pop("sub", None)
        scopes = extra.pop("scopes", None)
        once = extra.pop("once", False)
        jti = extra.pop("jti", None)
        return self._caps.mint(
            action,
            args,
            extra=extra or None,
            sub=sub,
            scopes=scopes,
            once=once,
            jti=jti,
        )

    def mint_loose(self, action: str, **extra: Any) -> str:
        return self.mint(action, {}, **extra)

    def bind_request(self, request: Any) -> None:
        """Host calls this before dispatch so auth_resolver can read the request.

        Uses a ContextVar so concurrent ASGI tasks do not clobber each other.
        """
        _request_var.set(request)

    def dispatch(
        self,
        intent: Intent | Mapping[str, Any],
        *,
        principal: Optional[Principal] = None,
    ) -> Result:
        token = None
        if principal is not None:
            token = _principal_override.set(principal)
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return self._dispatch_sync(intent)
            raise RuntimeError(
                "ActionRegistry.dispatch() called from a running event loop; "
                "use await registry.async_dispatch(intent) instead"
            )
        finally:
            if token is not None:
                _principal_override.reset(token)

    async def async_dispatch(
        self,
        intent: Intent | Mapping[str, Any],
        *,
        principal: Optional[Principal] = None,
    ) -> Result:
        """Awaitable dispatch. Same law as dispatch. Runs sync and async handlers."""
        token = None
        if principal is not None:
            token = _principal_override.set(principal)
        try:
            return await self._async_dispatch(intent)
        finally:
            if token is not None:
                _principal_override.reset(token)

    dispatch_async = async_dispatch

    def _resolve_principal(self) -> Optional[Principal]:
        override = _principal_override.get()
        if override is not None:
            return override
        if not self.auth_resolver:
            return None
        try:
            return self.auth_resolver(_request_var.get())
        except Exception as exc:
            logger.exception("auth_resolver failed")
            _sec(
                "auth_resolver_failed",
                action="",
                reason=str(exc) or type(exc).__name__,
            )
            raise AuthResolverFailed(str(exc) or type(exc).__name__) from exc

    def _prepare(
        self, intent: Intent | Mapping[str, Any]
    ) -> tuple[
        Intent,
        dict[str, Any],
        Optional[Result],
        Optional[Principal],
        Optional[dict],
        bool,
    ]:
        if not isinstance(intent, Intent):
            try:
                intent = Intent.from_dict(intent)
            except (ValueError, TypeError, KeyError) as exc:
                # malformed Intent — return structured failure (never raise to hosts)
                bad = Intent(action="?", args={})
                return (
                    bad,
                    {},
                    Result.failure("bad_request", f"invalid intent: {exc}"),
                    None,
                    None,
                    False,
                )

        if not intent.request_id:
            intent.request_id = "req_" + _trace_api().new_trace_id()[3:]

        try:
            validate_action_name(intent.action)
        except ValueError as exc:
            return (
                intent,
                {},
                Result.failure("bad_request", str(exc), action=intent.action, request_id=intent.request_id),
                None,
                None,
                False,
            )

        try:
            check_json_limits(intent.args or {})
            if intent.form:
                check_json_limits(intent.form)
        except JsonLimitError as exc:
            return (
                intent,
                {},
                Result.failure("bad_request", str(exc), action=intent.action, request_id=intent.request_id),
                None,
                None,
                False,
            )

        tr = _trace_api().get_tracer()
        tr.emit(
            _trace_api().FrameKind.INTENT_IN,
            f"intent {intent.action}",
            request_id=intent.request_id,
            action=intent.action,
            detail={
                "args": intent.args,
                "form_keys": list((intent.form or {}).keys()),
                "has_cap": bool(intent.cap),
                "target": intent.target,
                "idempotency_key": intent.idempotency_key,
            },
        )

        meta_base = {"action": intent.action, "request_id": intent.request_id}

        # Idempotency short-circuit
        if intent.idempotency_key and self.idempotency_store:
            try:
                cached = self.idempotency_store.get(intent.idempotency_key)
            except _RedisStoreError:
                logger.exception("idempotency store failed")
                return (
                    intent,
                    {},
                    Result.failure(
                        "unavailable",
                        "idempotency store failed",
                        retryable=True,
                        **{k: v for k, v in meta_base.items() if v is not None},
                    ),
                    None,
                    None,
                    False,
                )
            if cached is not None:
                tr.emit(
                    _trace_api().FrameKind.CUSTOM,
                    "idempotency hit",
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=cached.get("ok"),
                )
                cached_result = Result.from_dict(cached)
                return intent, {}, cached_result, None, None, True

        handler = self._actions.get(intent.action)
        if handler is None:
            tr.emit(
                _trace_api().FrameKind.HANDLER_ERROR,
                f"unknown action: {intent.action}",
                request_id=intent.request_id,
                action=intent.action,
                ok=False,
            )
            return (
                intent,
                {},
                Result.failure(
                    "not_found",
                    f"unknown action: {intent.action}",
                    **{k: v for k, v in meta_base.items() if v is not None},
                ),
                None,
                None,
                False,
            )

        args = dict(intent.args)
        if intent.form:
            for k, v in intent.form.items():
                args.setdefault(k, v)

        try:
            principal = self._resolve_principal()
        except AuthResolverFailed as exc:
            return (
                intent,
                args,
                Result.failure(
                    "unauthorized",
                    f"auth_resolver failed: {exc}",
                    **{k: v for k, v in meta_base.items() if v is not None},
                ),
                None,
                None,
                False,
            )
        # The principal comes only from dispatch(principal=) or auth_resolver.
        # Intent args are client data: no id, role or scope in them is identity.
        if principal is None and (
            args.get("roles") is not None or args.get("role") is not None
        ):
            # Emit so operators can see probes.
            _sec(
                "role_claim_ignored",
                action=intent.action,
                reason="roles in Intent.args are ignored; use auth_resolver / principal=",
            )
        if self.require_principal and principal is None:
            return (
                intent,
                args,
                Result.failure(
                    "unauthorized",
                    "authentication required — resolve principal or disable require_principal",
                    **{k: v for k, v in meta_base.items() if v is not None},
                ),
                None,
                None,
                False,
            )

        cap_data: Optional[dict] = None
        cap_present = bool(intent.cap)
        # present-cap-must-verify: a provided cap is never silently ignored,
        # even when require_cap=False (open action).
        if self.require_cap or cap_present:
            if not intent.cap:
                _sec("cap_fail", action=intent.action, reason="missing capability")
                tr.emit(
                    _trace_api().FrameKind.CAP_FAIL,
                    "missing capability",
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=False,
                )
                return (
                    intent,
                    args,
                    Result.failure(
                        "unauthorized",
                        "missing capability — use ch.control(action).as_dict() "
                        "on the control (Channel.help('ux-dom-control'))",
                        **{k: v for k, v in meta_base.items() if v is not None},
                    ),
                    principal,
                    None,
                    False,
                )
            verify_args = args if self.verify_form_in_cap else dict(intent.args)
            try:
                verify_kw: dict[str, Any] = {
                    "expected_sub": self._cap_expected_sub(principal),
                    # Consume after the rate-limit hook. Burning the nonce here
                    # makes a 429 retry look like a replay.
                    "consume_once": False,
                }
                if not self._cek_require_owns_once():
                    verify_kw["nonce_store"] = self.nonce_store
                cap_data = self._caps.verify(
                    intent.cap,
                    intent.action,
                    verify_args,
                    **verify_kw,
                )
                # A subject-bound Cap runs only for the authenticated principal
                # it names (cek-host claims "subject", classic CapService "sub").
                subject = cap_subject(cap_data)
                if subject is not None:
                    if principal is None:
                        raise CapError("capability subject requires an authenticated principal")
                    # A blank subject names nobody, so no principal matches it.
                    if not subject.strip() or principal.id != subject:
                        raise CapError("subject bind mismatch")
                tr.emit(
                    _trace_api().FrameKind.CAP_OK,
                    "capability verified",
                    request_id=intent.request_id,
                    action=intent.action,
                    detail={"sub": subject, "once": cap_data.get("once")},
                )
            except CapError as exc:
                _sec("cap_fail", action=getattr(intent, "action", ""), reason=str(exc))
                tr.emit(
                    _trace_api().FrameKind.CAP_FAIL,
                    str(exc),
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=False,
                )
                return (
                    intent,
                    args,
                    Result.failure(
                        "unauthorized",
                        str(exc),
                        **{k: v for k, v in meta_base.items() if v is not None},
                    ),
                    principal,
                    None,
                    False,
                )

        if (
            cap_data
            and cap_data.get("once")
            and not self._cek_require_owns_once()
        ):
            jti = str(cap_data.get("jti") or "").strip()
            nonce = self.nonce_store
            if nonce is None:
                nonce = getattr(self._caps, "nonce_store", None)
            if not jti:
                return (
                    intent,
                    args,
                    Result.failure(
                        "unauthorized",
                        "once capability missing jti",
                        **{k: v for k, v in meta_base.items() if v is not None},
                    ),
                    principal,
                    None,
                    False,
                )
            if nonce is None:
                return (
                    intent,
                    args,
                    Result.failure(
                        "unauthorized",
                        "once capability requires nonce_store "
                        "(configure MemoryNonceStore or RedisNonceStore)",
                        **{k: v for k, v in meta_base.items() if v is not None},
                    ),
                    principal,
                    None,
                    False,
                )

        # before-hooks run in _dispatch_sync / _async_dispatch (sync vs await)
        return intent, args, None, principal, cap_data, False

    def _finalize(
        self,
        intent: Intent,
        result: Result,
        t0: float,
        claim_token: Optional[str] = None,
        idempotency_hit: bool = False,
    ) -> Result:
        result.meta.setdefault("action", intent.action)
        if intent.request_id:
            result.meta.setdefault("request_id", intent.request_id)
        result.meta["duration_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        from ux_channel._version import __version__ as _ver
        result.meta.setdefault("runtime", _ver)
        tid = result.meta.get("trace_id")

        for hook in self.hooks.after:
            out = hook(intent, result)
            if inspect.isawaitable(out):
                close = getattr(out, "close", None)
                if callable(close):
                    close()
                raise AsyncDispatchRequired(
                    "async after-hook requires await registry.async_dispatch "
                    f"({getattr(hook, '__name__', type(hook).__name__)})"
                )
            # After-hooks must return a Result. None / wrong type used to
            # replace the real Result and crash in enforce_result_limits
            # ("NoneType has no attribute ops"). Keep prior Result instead.
            if out is None:
                continue
            if not isinstance(out, Result):
                logger.warning(
                    "after_hook_ignored action=%s hook=%s returned %s (expected Result)",
                    intent.action,
                    getattr(hook, "__name__", repr(hook)),
                    type(out).__name__,
                )
                continue
            result = out

        try:
            enforce_result_limits(
                result,
                max_html_bytes=self.max_html_bytes,
                max_ops=self.max_ops,
                max_result_bytes=self.max_result_bytes,
            )
        except LimitExceeded as exc:
            logger.error("payload_too_large action=%s err=%s", intent.action, exc)
            _trace_api().get_tracer().emit(
                _trace_api().FrameKind.LIMIT,
                f"payload_too_large: {exc}",
                request_id=intent.request_id,
                action=intent.action,
                ok=False,
            )
            from ux_channel.protocol.error_map import ensure_error_meta

            return ensure_error_meta(
                Result.failure(
                    "payload_too_large",
                    "response too large",
                    action=intent.action,
                    request_id=intent.request_id,
                )
            )

        # Store a success. The caller's finally releases the slot on every
        # path that did not replace the pending reservation, including this
        # failure. A client must not see ok=True while the slot is still pending.
        # A replay hit is already stored. The flag is a dispatch local, so an
        # after-hook that returns a new Result cannot drop it and rewrite.
        if (
            intent.idempotency_key
            and self.idempotency_store
            and result.ok
            and not idempotency_hit
        ):
            try:
                self.idempotency_store.set(
                    intent.idempotency_key,
                    result.to_dict(),
                    ttl_s=3600,
                    token=claim_token,
                )
            except IdempotencyCapacityError:
                from ux_channel.protocol.error_map import ensure_error_meta

                return ensure_error_meta(
                    Result.failure(
                        "unavailable",
                        "idempotency store is full",
                        retryable=True,
                        action=intent.action,
                        request_id=intent.request_id,
                    )
                )
            except _RedisStoreError:
                logger.exception("idempotency store failed")
                from ux_channel.protocol.error_map import ensure_error_meta

                return ensure_error_meta(
                    Result.failure(
                        "unavailable",
                        "idempotency store failed",
                        retryable=True,
                        action=intent.action,
                        request_id=intent.request_id,
                    )
                )
            except Exception:
                logger.exception("idempotency store failed")
                from ux_channel.protocol.error_map import ensure_error_meta

                return ensure_error_meta(
                    Result.failure(
                        "unavailable",
                        "idempotency store failed",
                        retryable=True,
                        action=intent.action,
                        request_id=intent.request_id,
                    )
                )

        # Href check and strict morph/swap/toast strip. Same function as
        # PushBus.publish, including ops nested in seq / timer.set / invoke.
        hosts = ()
        cfg = getattr(self, "config", None)
        if cfg is not None:
            hosts = tuple(getattr(cfg, "navigate_allowed_hosts", ()) or ())
        policy = "off"
        if cfg is not None:
            raw_policy = getattr(cfg, "morph_html_policy", None)
            if raw_policy is None:
                policy = "off"
            elif raw_policy not in ("off", "strict"):
                raise ValueError('morph_html_policy must be "off" or "strict"')
            else:
                policy = str(raw_policy)
        result.ops = filter_outbound_ops(
            list(result.ops),
            policy=policy,
            allowed_hosts=hosts,
            origin_host=_bound_origin_host(_request_var.get()),
        )

        tr = _trace_api().get_tracer()
        if tr.enabled:
            tr.record_result_ops(
                result,
                request_id=intent.request_id,
                action=intent.action,
                trace_id=tid if isinstance(tid, str) else None,
            )
            tr.emit(
                _trace_api().FrameKind.RESULT_OUT,
                f"result ok={result.ok} ops={len(result.ops)}",
                request_id=intent.request_id,
                action=intent.action,
                duration_ms=result.meta.get("duration_ms"),
                ok=result.ok,
                detail={
                    "error": result.error.to_dict() if result.error else None,
                    "op_kinds": [o.get("op") for o in result.ops if isinstance(o, dict)],
                },
                trace_id=tid if isinstance(tid, str) else None,
            )
        from ux_channel.protocol.error_map import ensure_error_meta

        return ensure_error_meta(result)

    def _encode(self, value: Any, intent: Intent, meta: dict[str, Any]) -> Result:
        return _call_encode_result(
            value,
            renderer=self._renderer,
            default_target=intent.target,
            meta={k: v for k, v in meta.items() if v is not None},
        )

    def _internal_message(self, exc: BaseException) -> str:
        if self.expose_internal_errors:
            return str(exc) or exc.__class__.__name__
        return "internal error"

    def _build_ctx(
        self,
        intent: Intent,
        principal: Optional[Principal],
        t0: float,
        args: Optional[Mapping[str, Any]] = None,
        cap_data: Optional[Mapping[str, Any]] = None,
    ) -> ActionContext:
        deadline = None
        if self.action_timeout_s and self.action_timeout_s > 0:
            deadline = time.monotonic() + self.action_timeout_s
        meta: dict[str, Any] = {}
        # Stamp resource / tenancy keys so RegionBook can rebuild scope without
        # depending on handler signature binding every key. Identity keys come
        # only from the principal, never from args.
        if args:
            for k, v in args.items():
                if v is None or k in IDENTITY_KEYS or k in ("roles", "role"):
                    continue
                if k.endswith("_id") or k in ("tenant_id", "id", "uid"):
                    meta[k] = v
        if principal is not None:
            for k in IDENTITY_KEYS:
                meta[k] = principal.id
        return ActionContext(
            request_id=intent.request_id or "",
            action=intent.action,
            principal=principal,
            deadline_monotonic=deadline,
            idempotency_key=intent.idempotency_key,
            request=_request_var.get(),
            meta=meta,
            verified=VerifiedContext.from_claims(cap_data) if cap_data else None,
        )

    def _bind_args(
        self,
        handler: ActionHandler,
        args: Mapping[str, Any],
        ctx: Optional[ActionContext] = None,
    ) -> dict[str, Any]:
        sig = inspect.signature(handler)
        accepts_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        bound: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            # inject ActionContext by name or annotation
            ann = param.annotation
            wants_ctx = name == "ctx" or (
                ann is not inspect.Parameter.empty
                and (ann is ActionContext or getattr(ann, "__name__", "") == "ActionContext")
            )
            if wants_ctx and ctx is not None:
                bound[name] = ctx
                continue
            # inject Principal when handler asks for it
            wants_principal = name == "principal" or (
                ann is not inspect.Parameter.empty
                and (ann is Principal or getattr(ann, "__name__", "") == "Principal")
            )
            if wants_principal:
                # Never bound from args: a client-sent "principal" is not one.
                if ctx is not None and ctx.principal is not None:
                    bound[name] = ctx.principal
                continue
            if name in args:
                bound[name] = args[name]
            elif param.default is not inspect.Parameter.empty:
                continue
            elif param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            else:
                raise TypeError(f"missing required argument: {name}")
        if accepts_var_kw:
            for k, v in args.items():
                if k != "principal":
                    bound.setdefault(k, v)
            # region wrappers expect principal in kwargs
            if ctx is not None and ctx.principal is not None:
                bound["principal"] = ctx.principal
        hints = {}
        try:
            hints = {
                k: v
                for k, v in getattr(handler, "__annotations__", {}).items()
                if k not in ("return", "ctx")
            }
        except Exception:
            hints = {}
        for k, v in list(bound.items()):
            if k == "ctx":
                continue
            ann = hints.get(k)
            if ann is int and isinstance(v, str) and v.lstrip("-").isdigit():
                bound[k] = int(v)
            elif ann is float and isinstance(v, str):
                try:
                    bound[k] = float(v)
                except ValueError:
                    pass
            elif ann is bool and isinstance(v, str):
                bound[k] = v.lower() in ("1", "true", "yes", "on")
        return bound


    def _run_before_hooks_sync(
        self,
        intent: Intent,
        args: dict[str, Any],
        principal: Optional[Principal],
        cap_data: Optional[dict],
    ) -> Optional[Result]:
        tr = _trace_api().get_tracer()
        for hook in self.hooks.before:
            early = hook(intent, args)
            if inspect.isawaitable(early):
                close = getattr(early, "close", None)
                if callable(close):
                    close()
                raise AsyncDispatchRequired(
                    "async before-hook requires await registry.async_dispatch "
                    f"({getattr(hook, '__name__', type(hook).__name__)})"
                )
            if early is not None:
                if not isinstance(early, Result):
                    raise TypeError(
                        f"before-hook must return Result or None, got {type(early).__name__}"
                    )
                tr.emit(
                    _trace_api().FrameKind.HOOK_SHORT,
                    f"before-hook short-circuit {type(hook).__name__}",
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=getattr(early, "ok", None),
                )
                return early
        return None

    async def _run_before_hooks_async(
        self,
        intent: Intent,
        args: dict[str, Any],
        principal: Optional[Principal],
        cap_data: Optional[dict],
    ) -> Optional[Result]:
        tr = _trace_api().get_tracer()
        for hook in self.hooks.before:
            early = hook(intent, args)
            if inspect.isawaitable(early):
                early = await early
            if early is not None:
                if not isinstance(early, Result):
                    raise TypeError(
                        f"before-hook must return Result or None, got {type(early).__name__}"
                    )
                tr.emit(
                    _trace_api().FrameKind.HOOK_SHORT,
                    f"before-hook short-circuit {type(hook).__name__}",
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=getattr(early, "ok", None),
                )
                return early
        return None


    def _call_sync_handler(self, handler: ActionHandler, bound: dict[str, Any]) -> Any:
        """Run sync handler; apply timeout; never drop awaitables silently."""
        timeout = self.action_timeout_s if self.action_timeout_s and self.action_timeout_s > 0 else None
        if timeout:
            import concurrent.futures
            import contextvars

            # CRITICAL: ThreadPoolExecutor does not inherit ContextVars.
            # auth=True wrappers read _principal_override; without copy_context,
            # dispatch(principal=…) always looks unauthenticated under timeout.
            ctx = contextvars.copy_context()

            def _run() -> Any:
                return ctx.run(self._run_sync_handler, handler, bound)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_run)
                try:
                    value = fut.result(timeout=timeout)
                except concurrent.futures.TimeoutError as exc:
                    raise TimeoutError("action timed out") from exc
        else:
            value = self._run_sync_handler(handler, bound)
        if inspect.isawaitable(value):
            raise AsyncDispatchRequired(
                "handler returned an awaitable; use await registry.async_dispatch(...) "
                "(sync dispatch does not run an event loop)"
            )
        return value

    async def _await_with_timeout(self, value: Any) -> Any:
        if self.action_timeout_s and self.action_timeout_s > 0:
            return await asyncio.wait_for(value, timeout=self.action_timeout_s)
        return await value

    def _is_rate_limited(self, result: Result) -> bool:
        return bool(result.error and result.error.code == "rate_limited")

    def _cap_expected_sub(self, principal: Optional[Principal]) -> Optional[str]:
        """Caller id the verifier checks a Cap subject against.

        The cek-runtime Host checks the subject of every subject-bound Cap, so
        it always gets the caller. Classic CapService gets it only on
        ``bind_cap_to_principal``, which then also refuses a Cap with no
        subject; ``_prepare`` checks a classic Cap's subject either way.
        """
        if principal is None:
            return None
        if self._cek_require_owns_once() or getattr(
            self.config, "bind_cap_to_principal", False
        ):
            return principal.id
        return None

    def _consume_presented_once(
        self,
        intent: Intent,
        args: dict[str, Any],
        principal: Optional[Principal],
        cap_data: Optional[dict],
    ) -> Optional[Result]:
        """Burn a once-cap. Call only after the rate-limit check has passed."""
        if not cap_data or not cap_data.get("once") or not intent.cap:
            return None
        meta = {
            k: v
            for k, v in {"action": intent.action, "request_id": intent.request_id}.items()
            if v is not None
        }
        verify_args = args if self.verify_form_in_cap else dict(intent.args)
        try:
            verify_kw: dict[str, Any] = {
                "expected_sub": self._cap_expected_sub(principal),
                "consume_once": True,
            }
            if not self._cek_require_owns_once():
                verify_kw["nonce_store"] = self.nonce_store
            self._caps.verify(intent.cap, intent.action, verify_args, **verify_kw)
        except CapError as exc:
            _sec("cap_fail", action=intent.action, reason=str(exc))
            return Result.failure("unauthorized", str(exc), **meta)
        return None

    def _idem_release(self, key: Optional[str], token: Optional[str]) -> None:
        """Release only the reservation identified by ``token``."""
        store = self.idempotency_store
        if not key or not token or store is None:
            return
        release = getattr(store, "release", None)
        if release is None:
            return
        try:
            release(key, token)
        except _RedisStoreError:
            logger.exception("idempotency release failed")

    def _idem_begin(
        self, intent: Intent
    ) -> tuple[Optional[Result], Optional[str], bool]:
        """Reserve an idempotency slot before the handler.

        Returns ``(stop_result, claim_token, idempotency_hit)``. The token
        and the hit flag stay locals of this dispatch. The token is not
        stored in a context var, so a nested dispatch of the same key cannot
        release the parent slot.
        """
        key = intent.idempotency_key
        store = self.idempotency_store
        if not key or store is None or not hasattr(store, "claim"):
            return None, None, False
        meta = {
            k: v
            for k, v in {"action": intent.action, "request_id": intent.request_id}.items()
            if v is not None
        }
        try:
            claimed = store.claim(key)
        except IdempotencyCapacityError:
            return (
                Result.failure(
                    "unavailable",
                    "idempotency store is full",
                    retryable=True,
                    **meta,
                ),
                None,
                False,
            )
        except _RedisStoreError:
            logger.exception("idempotency store failed")
            return (
                Result.failure(
                    "unavailable",
                    "idempotency store failed",
                    retryable=True,
                    **meta,
                ),
                None,
                False,
            )
        status = claimed[0]
        body = claimed[1] if len(claimed) > 1 else None
        token = claimed[2] if len(claimed) > 2 else None
        if status == "hit" and isinstance(body, dict):
            return Result.from_dict(body), None, True
        if status == "pending":
            return (
                Result.failure(
                    "unavailable",
                    "idempotency key in progress",
                    retryable=True,
                    **meta,
                ),
                None,
                False,
            )
        if status == "reserved":
            return None, token, False
        return None, None, False

    def _admit_after_hooks(
        self,
        intent: Intent,
        args: dict[str, Any],
        principal: Optional[Principal],
        cap_data: Optional[dict],
        early: Optional[Result],
    ) -> tuple[Optional[Result], Optional[str], bool]:
        """Rate-limit, then idempotency reserve, then once-consume.

        A rate-limited request does not burn a once-cap. A full idempotency
        map refuses the call before the handler and before the nonce burn.
        """
        if early is not None:
            if not self._is_rate_limited(early):
                burned = self._consume_presented_once(intent, args, principal, cap_data)
                if burned is not None:
                    return burned, None, False
            return early, None, False
        stop, reserved, hit = self._idem_begin(intent)
        if stop is not None:
            return stop, None, hit
        burned = self._consume_presented_once(intent, args, principal, cap_data)
        if burned is not None:
            return burned, reserved, False
        return None, reserved, False

    def _lock_for_key(self, key: Any) -> Optional[threading.RLock]:
        """Return the lock for ``key``, or None when ``key`` cannot be weak."""
        try:
            lock = self._owner_locks.get(key)
        except TypeError:
            return None
        if lock is not None:
            return lock
        lock = threading.RLock()
        try:
            self._owner_locks[key] = lock
        except TypeError:
            return None
        return lock

    def _owner_lock(self, handler: ActionHandler) -> threading.RLock:
        owner = _sync_owner(handler)
        with self._owner_locks_guard:
            lock = self._lock_for_key(owner)
            if lock is not None:
                return lock
            # Slotted instances with no ``__weakref__`` cannot live in a
            # WeakKeyDictionary. Share one lock per type: coarser, and the
            # class does not keep the instance alive.
            lock = self._lock_for_key(type(owner))
            if lock is None:
                lock = threading.RLock()
                self._owner_locks[type(owner)] = lock
            return lock

    def _run_sync_handler(self, handler: ActionHandler, bound: dict[str, Any]) -> Any:
        """Run one sync handler under its owner's lock.

        The owner is the bound component (``handler.__self__``) or, for a
        plain function, the function itself. Different owners do not wait on
        each other. The lock is re-entrant, so the same thread may dispatch
        again. A cross-thread re-dispatch to the same owner waits up to
        ``sync_lock_timeout_s`` (default 30s) and then raises
        ``SyncLockTimeout`` instead of waiting forever. It can still wait
        for that timeout. An owner that cannot be weakly referenced (a
        slotted instance with no ``__weakref__``) shares the lock of its
        type with every other such instance.
        """
        lock = self._owner_lock(handler)
        timeout = float(self.sync_lock_timeout_s)
        if not lock.acquire(timeout=max(0.0, timeout)):
            raise SyncLockTimeout(timeout)
        try:
            return handler(**bound)
        finally:
            lock.release()

    def _dispatch_sync(self, intent_in: Intent | Mapping[str, Any]) -> Result:
        t0 = time.perf_counter()
        intent, args, early, principal, _cap, idempotency_hit = self._prepare(
            intent_in
        )
        if early is not None:
            return self._finalize(
                intent, early, t0, idempotency_hit=idempotency_hit
            )

        # An auth_resolver principal must be visible to auth wraps / RegionBook
        # (they read ContextVar; principal= on dispatch already set it).
        resolver_token = None
        claim_token: Optional[str] = None
        if principal is not None and _principal_override.get() is None:
            resolver_token = _principal_override.set(principal)
        try:
            early = self._run_before_hooks_sync(intent, args, principal, _cap)
            stop, claim_token, idempotency_hit = self._admit_after_hooks(
                intent, args, principal, _cap, early
            )
            if stop is not None:
                return self._finalize(
                    intent,
                    stop,
                    t0,
                    claim_token=claim_token,
                    idempotency_hit=idempotency_hit,
                )

            handler = self._actions[intent.action]
            meta = {"action": intent.action, "request_id": intent.request_id}
            ctx = self._build_ctx(intent, principal, t0, args, _cap)

            try:
                bound = self._bind_args(handler, args, ctx)
                if inspect.iscoroutinefunction(handler):
                    raise AsyncDispatchRequired(
                        f"action {intent.action!r} is async; use await registry.async_dispatch(...) "
                        "(sync dispatch does not run an event loop)"
                    )
                value = self._call_sync_handler(handler, bound)
            except ActionError as exc:
                result = _call_encode_result(exc, renderer=self._renderer, meta=meta)
                return self._finalize(intent, result, t0, claim_token=claim_token)
            except AsyncDispatchRequired:
                raise
            except SyncLockTimeout as exc:
                return self._finalize(
                    intent,
                    Result.failure(
                        "timeout",
                        str(exc),
                        retryable=True,
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except TypeError as exc:
                return self._finalize(
                    intent,
                    Result.failure(
                        "bad_request",
                        f"invalid action arguments: {exc}",
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except (asyncio.TimeoutError, TimeoutError):
                logger.error("action_timeout action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "timeout",
                        "action timed out",
                        retryable=True,
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("action_internal action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "internal",
                        self._internal_message(exc),
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )

            try:
                result = self._encode(value, intent, meta)
            except Exception as exc:  # noqa: BLE001
                logger.exception("encode_error action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "encode_error",
                        self._internal_message(exc),
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            return self._finalize(intent, result, t0, claim_token=claim_token)
        finally:
            self._idem_release(intent.idempotency_key, claim_token)
            if resolver_token is not None:
                _principal_override.reset(resolver_token)

    async def _join_cancelled_thread(self, work: "asyncio.Future[Any]") -> Any:
        """Wait until a shielded sync worker finishes.

        Another cancellation is cleared so this wait can run to completion.
        The caller re-raises ``CancelledError`` afterwards.
        """
        while not work.done():
            try:
                return await work
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is None:
                    raise
                while current.cancelling():
                    current.uncancel()
        return work.result()

    async def _finish_sync_worker_after_cancel(
        self,
        work: "asyncio.Future[Any]",
        intent: Intent,
        meta: dict[str, Any],
        t0: float,
        claim_token: Optional[str],
    ) -> None:
        """Store the worker's result, or leave a failure for ``finally`` to release."""
        try:
            value = await self._join_cancelled_thread(work)
            if inspect.isawaitable(value):
                value = await value
            result = self._encode(value, intent, meta)
            self._finalize(intent, result, t0, claim_token=claim_token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sync handler cancelled action=%s", intent.action)

    async def _run_with_timeout(self, handler: ActionHandler, bound: dict[str, Any]) -> Any:
        if self.action_timeout_s and self.action_timeout_s > 0:
            return await asyncio.wait_for(handler(**bound), timeout=self.action_timeout_s)
        return await handler(**bound)

    async def _async_dispatch(self, intent_in: Intent | Mapping[str, Any]) -> Result:
        t0 = time.perf_counter()
        intent, args, early, principal, _cap, idempotency_hit = self._prepare(
            intent_in
        )
        if early is not None:
            return self._finalize(
                intent, early, t0, idempotency_hit=idempotency_hit
            )

        resolver_token = None
        claim_token: Optional[str] = None
        if principal is not None and _principal_override.get() is None:
            resolver_token = _principal_override.set(principal)
        try:
            early = await self._run_before_hooks_async(intent, args, principal, _cap)
            stop, claim_token, idempotency_hit = self._admit_after_hooks(
                intent, args, principal, _cap, early
            )
            if stop is not None:
                return self._finalize(
                    intent,
                    stop,
                    t0,
                    claim_token=claim_token,
                    idempotency_hit=idempotency_hit,
                )

            handler = self._actions[intent.action]
            meta = {"action": intent.action, "request_id": intent.request_id}
            ctx = self._build_ctx(intent, principal, t0, args, _cap)

            try:
                bound = self._bind_args(handler, args, ctx)
                tr = _trace_api().get_tracer()
                tr.emit(
                    _trace_api().FrameKind.HANDLER_START,
                    f"handler {intent.action}",
                    request_id=intent.request_id,
                    action=intent.action,
                    detail={
                        "async": inspect.iscoroutinefunction(handler),
                        "arg_keys": [k for k in bound.keys() if k != "ctx"],
                        "principal": principal.id if principal else None,
                    },
                )
                t_handler = time.perf_counter()
                if inspect.iscoroutinefunction(handler):
                    value = await self._run_with_timeout(handler, bound)
                else:
                    # Preserve ContextVars (principal) across threads
                    # (asyncio.to_thread does not copy context on all Pythons).
                    ctx_run = contextvars.copy_context()
                    work = asyncio.create_task(
                        asyncio.to_thread(
                            ctx_run.run, self._run_sync_handler, handler, bound
                        )
                    )
                    try:
                        value = await asyncio.shield(work)
                    except asyncio.CancelledError:
                        # The worker keeps running after this task is cancelled.
                        # Wait for it before the finally releases the slot, then
                        # store a success or leave the slot pending so finally
                        # can release it. The caller still sees CancelledError.
                        await self._finish_sync_worker_after_cancel(
                            work, intent, meta, t0, claim_token
                        )
                        raise
                    if inspect.isawaitable(value):
                        value = await value  # type: ignore[misc]
                tr.emit(
                    _trace_api().FrameKind.HANDLER_END,
                    f"handler done {intent.action}",
                    request_id=intent.request_id,
                    action=intent.action,
                    duration_ms=round((time.perf_counter() - t_handler) * 1000, 3),
                    ok=True,
                    detail={"return_type": type(value).__name__},
                )
            except ActionError as exc:
                result = _call_encode_result(exc, renderer=self._renderer, meta=meta)
                return self._finalize(intent, result, t0, claim_token=claim_token)
            except SyncLockTimeout as exc:
                return self._finalize(
                    intent,
                    Result.failure(
                        "timeout",
                        str(exc),
                        retryable=True,
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except TypeError as exc:
                return self._finalize(
                    intent,
                    Result.failure(
                        "bad_request",
                        f"invalid action arguments: {exc}",
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except (asyncio.TimeoutError, TimeoutError):
                logger.error("action_timeout action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "timeout",
                        "action timed out",
                        retryable=True,
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("action_internal action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "internal",
                        self._internal_message(exc),
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )

            try:
                result = self._encode(value, intent, meta)
            except Exception as exc:  # noqa: BLE001
                logger.exception("encode_error action=%s", intent.action)
                return self._finalize(
                    intent,
                    Result.failure(
                        "encode_error",
                        self._internal_message(exc),
                        **{k: v for k, v in meta.items() if v is not None},
                    ),
                    t0,
                )
            return self._finalize(intent, result, t0, claim_token=claim_token)
        finally:
            self._idem_release(intent.idempotency_key, claim_token)
            if resolver_token is not None:
                _principal_override.reset(resolver_token)


__all__ = ["ActionRegistry", "Navigate", "ActionHandler"]
