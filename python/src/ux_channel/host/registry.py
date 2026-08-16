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
import time
from typing import Any, Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from ux_channel.protocol.capability import CapError, CapService
from ux_channel.host.context import ActionContext, AuthResolver, Principal
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

from ux_channel.host.idempotency import IdempotencyStore
from ux_channel.security.limits import (
    DEFAULT_MAX_HTML_BYTES,
    DEFAULT_MAX_OPS,
    DEFAULT_MAX_RESULT_BYTES,
    LimitExceeded,
    enforce_result_limits,
)
from ux_channel.host.nonce import NonceStore
from ux_channel.security.security import sanitize_op_hrefs, validate_action_name


class AsyncDispatchRequired(TypeError):
    """Raised when sync dispatch meets an async handler or hook."""


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
        Replay protection for once-caps and client idempotency keys.
    auth_resolver:
        Optional request → Principal.
    action_timeout_s:
        Wall-clock limit per action (0 = none).

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
        # optional request stashed by host for auth_resolver

    @property
    def nonce_store(self) -> Optional[NonceStore]:
        return self._nonce_store

    @nonce_store.setter
    def nonce_store(self, store: Optional[NonceStore]) -> None:
        self._nonce_store = store
        self._caps.nonce_store = store

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
            from ux_channel.devtools.trace import TraceConfig, get_tracer

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
        raise RuntimeError(
            "ActionRegistry.dispatch() called from a running event loop; "
            "use await registry.async_dispatch(intent) instead"
        )

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
        except Exception:
            logger.exception("auth_resolver failed")
            return None

    def _prepare(
        self, intent: Intent | Mapping[str, Any]
    ) -> tuple[Intent, dict[str, Any], Optional[Result], Optional[Principal], Optional[dict]]:
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
            cached = self.idempotency_store.get(intent.idempotency_key)
            if cached is not None:
                tr.emit(
                    _trace_api().FrameKind.CUSTOM,
                    "idempotency hit",
                    request_id=intent.request_id,
                    action=intent.action,
                    ok=cached.get("ok"),
                )
                return intent, {}, Result.from_dict(cached), None, None

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
            )

        args = dict(intent.args)
        if intent.form:
            for k, v in intent.form.items():
                args.setdefault(k, v)

        principal = self._resolve_principal()
        soft_from_args = False
        # Soft identity: id only. NEVER take roles/scopes from client Intent args.
        if principal is None:
            # Client-supplied roles are never trusted — emit so operators can see probes.
            if args.get("roles") is not None or args.get("role") is not None:
                _sec(
                    "role_claim_ignored",
                    action=intent.action,
                    reason="roles in Intent.args are ignored; use auth_resolver / principal=",
                    principal=str(
                        args.get("user_id") or args.get("sub") or args.get("subject") or ""
                    ),
                )
            for key in ("user_id", "sub", "subject"):
                val = args.get(key)
                if val is not None and str(val).strip():
                    principal = Principal.of(str(val).strip())
                    soft_from_args = True
                    break
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
                )
            verify_args = args if self.verify_form_in_cap else dict(intent.args)
            try:
                cap_data = self._caps.verify(
                    intent.cap,
                    intent.action,
                    verify_args,
                    expected_sub=principal.id if principal and getattr(
                        self.config, "bind_cap_to_principal", False
                    ) else None,
                    consume_once=True,
                    nonce_store=self.nonce_store,
                )
                tr.emit(
                    _trace_api().FrameKind.CAP_OK,
                    "capability verified",
                    request_id=intent.request_id,
                    action=intent.action,
                    detail={"sub": cap_data.get("sub"), "once": cap_data.get("once")},
                )
                # Cap subject is server-signed truth: fill missing principal, or
                # override soft-from-args when they disagree (never trust client id
                # over a signed sub).
                cap_sub = cap_data.get("sub")
                if cap_sub is not None and str(cap_sub).strip():
                    cap_sub_s = str(cap_sub).strip()
                    if principal is None:
                        principal = Principal(id=cap_sub_s)
                    elif soft_from_args and str(getattr(principal, "id", "") or "") != cap_sub_s:
                        _sec(
                            "principal_mismatch",
                            action=intent.action,
                            reason="soft principal from args differed from cap.sub; using cap.sub",
                            principal=cap_sub_s,
                            claimed=str(getattr(principal, "id", "") or ""),
                        )
                        principal = Principal(id=cap_sub_s)
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
                )

        # before-hooks run in _dispatch_sync / _async_dispatch (sync vs await)
        return intent, args, None, principal, cap_data

    def _finalize(self, intent: Intent, result: Result, t0: float) -> Result:
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

        # store idempotent success/failure
        if intent.idempotency_key and self.idempotency_store and result.ok:
            try:
                self.idempotency_store.set(
                    intent.idempotency_key, result.to_dict(), ttl_s=3600
                )
            except Exception:
                logger.exception("idempotency store failed")

        # Drop javascript:/data: navigations even if action built raw dicts
        hosts = ()
        cfg = getattr(self, "config", None)
        if cfg is not None:
            hosts = tuple(getattr(cfg, "navigate_allowed_hosts", ()) or ())
        result.ops = sanitize_op_hrefs(list(result.ops), allowed_hosts=hosts)
        # Opt-in morph HTML policy (SECURITY_AUDIT HIGH residual). Default off.
        policy = "off"
        if cfg is not None:
            policy = str(getattr(cfg, "morph_html_policy", "off") or "off")
        if policy == "strict":
            from ux_channel.render.morph_policy import apply_morph_policy

            result.ops = apply_morph_policy(list(result.ops), policy=policy)

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
    ) -> ActionContext:
        deadline = None
        if self.action_timeout_s and self.action_timeout_s > 0:
            deadline = time.monotonic() + self.action_timeout_s
        meta: dict[str, Any] = {}
        # Stamp identity / tenancy keys so RegionBook can rebuild scope without
        # depending on handler signature binding every key.
        if args:
            for k, v in args.items():
                if v is None:
                    continue
                if k in ("roles", "role"):
                    continue
                if k.endswith("_id") or k in (
                    "user_id", "sub", "subject", "tenant_id", "id", "uid",
                ):
                    meta[k] = v
        if principal is not None:
            pid = getattr(principal, "id", None) or getattr(principal, "sub", None)
            if pid:
                meta.setdefault("user_id", pid)
                meta.setdefault("subject", pid)
                meta.setdefault("sub", pid)
        return ActionContext(
            request_id=intent.request_id or "",
            action=intent.action,
            principal=principal,
            deadline_monotonic=deadline,
            idempotency_key=intent.idempotency_key,
            request=_request_var.get(),
            meta=meta,
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
            if wants_principal and ctx is not None and ctx.principal is not None:
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
                bound.setdefault(k, v)
            # region wrappers expect principal in kwargs
            if ctx is not None and ctx.principal is not None:
                bound.setdefault("principal", ctx.principal)
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
                return ctx.run(handler, **bound)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_run)
                try:
                    value = fut.result(timeout=timeout)
                except concurrent.futures.TimeoutError as exc:
                    raise TimeoutError("action timed out") from exc
        else:
            value = handler(**bound)
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

    def _dispatch_sync(self, intent_in: Intent | Mapping[str, Any]) -> Result:
        t0 = time.perf_counter()
        intent, args, early, principal, _cap = self._prepare(intent_in)
        if early is not None:
            return self._finalize(intent, early, t0)

        # Soft principal from args must be visible to auth wraps / RegionBook
        # (they read ContextVar; principal= on dispatch already set it).
        soft_token = None
        if principal is not None and _principal_override.get() is None:
            soft_token = _principal_override.set(principal)
        try:
            early = self._run_before_hooks_sync(intent, args, principal, _cap)
            if early is not None:
                return self._finalize(intent, early, t0)

            handler = self._actions[intent.action]
            meta = {"action": intent.action, "request_id": intent.request_id}
            ctx = self._build_ctx(intent, principal, t0, args)

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
                return self._finalize(intent, result, t0)
            except AsyncDispatchRequired:
                raise
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
            return self._finalize(intent, result, t0)
        finally:
            if soft_token is not None:
                _principal_override.reset(soft_token)

    async def _run_with_timeout(self, handler: ActionHandler, bound: dict[str, Any]) -> Any:
        if self.action_timeout_s and self.action_timeout_s > 0:
            return await asyncio.wait_for(handler(**bound), timeout=self.action_timeout_s)
        return await handler(**bound)

    async def _async_dispatch(self, intent_in: Intent | Mapping[str, Any]) -> Result:
        t0 = time.perf_counter()
        intent, args, early, principal, _cap = self._prepare(intent_in)
        if early is not None:
            return self._finalize(intent, early, t0)

        soft_token = None
        if principal is not None and _principal_override.get() is None:
            soft_token = _principal_override.set(principal)
        try:
            early = await self._run_before_hooks_async(intent, args, principal, _cap)
            if early is not None:
                return self._finalize(intent, early, t0)

            handler = self._actions[intent.action]
            meta = {"action": intent.action, "request_id": intent.request_id}
            ctx = self._build_ctx(intent, principal, t0, args)

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
                    # Preserve ContextVars (soft/hard principal) across threads
                    # (asyncio.to_thread does not copy context on all Pythons).
                    ctx_run = contextvars.copy_context()
                    value = await asyncio.to_thread(ctx_run.run, lambda: handler(**bound))
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
                return self._finalize(intent, result, t0)
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
            return self._finalize(intent, result, t0)
        finally:
            if soft_token is not None:
                _principal_override.reset(soft_token)


__all__ = ["ActionRegistry", "Navigate", "ActionHandler"]
