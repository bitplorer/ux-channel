"""
Flow — product verbs on Channel: on, done, fail, refresh.

First principles
----------------
Handlers should speak **outcomes**, not hand-assemble ops every time:

- ``ch.done(...)`` — success path (optional notice + refresh list)
- ``ch.fail.valid / auth / rate / ...`` — structured failures
- ``ch.done(refresh=[...])`` — re-render regions into morph ops (success path)
- ``ch.refresh(*uids)`` — power: same as done(refresh=uids)
- ``@ch.on`` — register actions with refresh/auth/idempotent metadata

``attach_flow(channel)`` binds these onto the Channel instance at boot.
Internal plumbing still calls ``RegionBook.revalidate``; **product speech**
is always ``refresh``.

FailFlow methods (closed set)
-----------------------------
valid, auth, forbidden, rate, plus ``code(name, …)`` for not_found / conflict / internal / …

No aliases — use the short intent names (``valid`` not ``validation``).

See: docs/HOW_TO.md, docs/ERRORS.md.
"""


from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from ux_channel.protocol.types import Result

Handler = Callable[..., Any]


def resolve_uid(uid: Any) -> str:
    """Accept string or region function (``.uid``)."""
    if isinstance(uid, str):
        return uid
    u = getattr(uid, "uid", None)
    if u is not None:
        return str(u)
    raise TypeError(f"refresh target must be str or region fn, got {type(uid)!r}")


def resolve_uids(uids: Sequence[Any]) -> list[str]:
    return [resolve_uid(u) for u in uids]



class FailFlow:
    """
    Structured failure builders attached as ``ch.fail``.

    First principles
    ----------------
    Failures are still Results: ``ok=False`` plus a stable ``error.code`` so
    HTTP mapping and the client error plane stay consistent. Optional morph
    ops keep the form on-screen with field errors.

    Closed method set (no aliases)
    ------------------------------
    ``valid`` — validation + fields (HTTP 422)
    ``auth`` — unauthorized (401)
    ``forbidden`` — 403
    ``rate`` — rate_limited, retryable (429)
    ``code(code, message)`` — any stable error code (not_found, conflict, internal, …)

    Example::

        return ch.fail.valid(
            {"email": ["required"]},
            region="Form:root",
            html=form_html,
            message="Fix the form",
        )
        return ch.fail.auth("Sign in")
        return ch.fail.rate("Slow down")

    Stock toast overlays only when ``notice=True``.
    """

    def __init__(self, channel: Any):
        self._ch = channel

    def auth(self, message: str = "Please sign in", *, notice: bool = False) -> Result:
        return self._fail("unauthorized", message, notice=notice, level="error")

    def forbidden(self, message: str = "Forbidden", *, notice: bool = False) -> Result:
        return self._fail("forbidden", message, notice=notice, level="error")

    def rate(self, message: str = "Too many requests", *, notice: bool = False) -> Result:
        return self._fail("rate_limited", message, notice=notice, level="warning")


    def valid(
        self,
        fields: dict[str, list[str]],
        *,
        region: str,
        html: Any,
        message: str = "Please fix the highlighted fields",
        focus: Optional[str] = None,
        notice: bool = False,
    ) -> Result:
        html_s = html if isinstance(html, str) else str(html)
        b = self._ch.ui.region(region, html_s)
        if focus:
            b.focus(focus, select=True)
        if notice:
            b.toast(message, level="error")
        return b.fail("validation", message, fields=fields)


    def code(self, code: str, message: str, *, notice: bool = False, **kwargs: Any) -> Result:
        return self._fail(code, message, notice=notice, level="error", **kwargs)

    def _fail(
        self,
        code: str,
        message: str,
        *,
        notice: bool,
        level: str = "error",
        **kwargs: Any,
    ) -> Result:
        if notice:
            return self._ch.ui.toast(message, level=level).fail(code, message, **kwargs)
        return Result.failure(code, message, **kwargs)


class DraftBag:
    """
    Ephemeral UI drafts — not business truth.

    ``get`` / ``set`` are each atomic; the **pair** is not (see ``state`` module).

    Preferred patterns::

        # feels like get/set — CAS commit on exit
        with ch.draft.edit("n", default=0) as slot:
            slot.value += 1

        # same inside async actions
        async with ch.draft.edit("n", default=0) as slot:
            slot.value += 1

        # pure transform under the store lock
        ch.draft.change("n", lambda n: n + 1, default=0)

        # dict fields
        ch.draft.merge("form", email=email, name=name)
    """

    def __init__(self, channel: Any):
        self._ch = channel

    def get(self, key: str, default: Any = None) -> Any:
        return self._ch.state.get(key, default=default)

    def set(self, key: str, value: Any) -> None:
        self._ch.state.set(key, value)

    def clear(self, key: str) -> None:
        self._ch.state.delete(key)

    def edit(self, key: str, *, default: Any = None) -> Any:
        """Context manager: mutate ``slot.value``, atomic CAS commit on exit."""
        return self._ch.state.edit(key, default=default)

    def edit_retry(self, key: str, fn: Any, *, default: Any = None, retries: int = 32) -> Any:
        """CAS apply with retries — safer under concurrent writers than bare edit."""
        store = self._ch.state
        if hasattr(store, "edit_retry"):
            return store.edit_retry(key, fn, default=default, retries=retries)
        # Fallback: change if available (locked for memory)
        if hasattr(store, "change"):
            return store.change(key, fn, default=default)
        last = None
        for _ in range(retries):
            try:
                with store.edit(key, default=default) as slot:
                    slot.value = fn(slot.value)
                return store.get(key, default)
            except Exception as exc:
                last = exc
                continue
        raise last  # type: ignore[misc]


    def change(self, key: str, mutator: Any, *, default: Any = None) -> Any:
        """Atomic transform under the store lock."""
        return self._ch.state.change(key, mutator, default=default)

    def merge(self, key: str, **fields: Any) -> Any:
        """Atomic dict field merge."""
        return self._ch.state.merge(key, fields, default={})



    def incr(self, key: str, delta: float = 1, *, default: float = 0) -> float:
        """Counter sugar → ``change(key, lambda n: n + delta)``."""
        return self._ch.state.incr(key, delta, default=default)

class Flow:
    def __init__(self, channel: Any):
        self.ch = channel
        self.fail = FailFlow(channel)
        self.draft = DraftBag(channel)
        self._refresh_uids: list[str] = []
        self._refresh_principal: Any = None
        self._refresh_scope: dict[str, Any] = {}

    def push_refresh(
        self,
        uids: Sequence[str],
        *,
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._refresh_uids = resolve_uids(uids)
        self._refresh_principal = principal
        self._refresh_scope = dict(scope or {})

    def clear_refresh(self) -> None:
        self._refresh_uids = []
        self._refresh_scope = {}
        self._refresh_principal = None

    def done(
        self,
        notice: Optional[str] = None,
        *,
        refresh: Optional[Sequence[Any]] = None,
        notice_level: str = "info",
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        go: Optional[str] = None,
        etags: Optional[Mapping[str, str]] = None,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> Result:
        """
        Success Result: optional region reload, notice (→ toast op), go (→ navigate).

        * ``refresh=None`` — use ``@ch.on(refresh=[...])`` stack when present
        * ``refresh=[]`` — force no reload
        * ``refresh=[uids…]`` — reload exactly these regions
        * ``meta`` — Result.meta (diagnostics only; never secrets)

        Product kwargs only: notice / notice_level / refresh / scope / principal / go / etags / meta.
        """
        uids = resolve_uids(refresh) if refresh is not None else list(self._refresh_uids)
        princ = principal if principal is not None else self._refresh_principal
        sc = dict(self._refresh_scope)
        if scope:
            sc.update(scope)

        book = self.ch.regions
        if uids:
            r = book.revalidate(
                *uids,
                principal=princ,
                scope=sc or None,
                toast=notice,
                toast_level=notice_level,
                etags=etags,
            )
        elif notice:
            r = self.ch.ui.toast(notice, level=notice_level).ok()
        else:
            r = Result.success()

        if meta:
            r = Result(
                v=getattr(r, "v", "1") or "1",
                ok=bool(r.ok),
                ops=list(r.ops or []),
                error=r.error,
                meta={**(r.meta or {}), **dict(meta)},
            )

        if go:
            from ux_channel.protocol.ops import navigate as nav_op

            ops = list(r.ops or [])
            nav = nav_op(go)
            # Do not clobber render_error / other failures with a fresh ok Result.
            if not getattr(r, "ok", True):
                ops = list(ops) + [nav]
                return Result(
                    v=getattr(r, "v", "1") or "1",
                    ok=False,
                    ops=ops,
                    error=r.error,
                    meta=dict(r.meta or {}),
                )
            ops.append(nav)
            # Preserve meta (e.g. refresh_errors) on success path too
            base = Result.success(*ops)
            if r.meta:
                return Result(
                    v=base.v,
                    ok=True,
                    ops=list(base.ops),
                    error=None,
                    meta={**(r.meta or {}), **(base.meta or {})},
                )
            return base
        return r

    def refresh(
        self,
        *uids: Any,
        notice: Optional[str] = None,
        notice_level: str = "info",
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        etags: Optional[Mapping[str, str]] = None,
    ) -> Result:
        """
        Power: reload regions from loaders → morph ops.

        Prefer ``return ch.done(refresh=[...])`` in handlers (single success path).
        This is ``done(refresh=uids)`` with no extra outcome flags required.
        """
        return self.done(
            notice,
            refresh=uids,
            notice_level=notice_level,
            principal=principal,
            scope=scope,
            etags=etags,
        )


    def notice(
        self,
        message: str,
        *uids: str,
        level: str = "info",
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
    ) -> Result:
        """Stock overlay message (+ optional region refresh). Prefer done(notice=)."""
        if uids:
            return self.refresh(
                *uids,
                notice=message,
                notice_level=level,
                principal=principal,
                scope=scope,
            )
        return self.ch.ui.toast(message, level=level).ok()


    def filter(
        self,
        *uids: str,
        q: str = "",
        principal: Any = None,
        **scope: Any,
    ) -> Result:
        """Re-render list regions with q in scope (power list filter)."""
        scope = dict(scope)
        scope["q"] = q
        return self.refresh(*uids, principal=principal, scope=scope)



def _principal_from_call(*args: Any, **kwargs: Any) -> Any:
    """Resolve principal from kwargs, ctx, or dispatch ContextVar (thread-safe with copy_context)."""
    principal = kwargs.get("principal")
    ctx = kwargs.get("ctx")
    if principal is None and ctx is not None:
        principal = getattr(ctx, "principal", None)
    if principal is None:
        try:
            from ux_channel.host.registry import _principal_override
            principal = _principal_override.get()
        except Exception:
            principal = None
    return principal


def _auth_wrap(ch: Any, fn: Handler) -> Handler:
    import inspect
    import functools

    def _resolve_uid(*args: Any, **kwargs: Any):
        ctx = kwargs.get("ctx")
        principal = kwargs.get("principal")
        # Dispatch may inject principal via ContextVar without putting it in kwargs
        # (handler signatures often omit principal/ctx).
        if principal is None:
            try:
                from ux_channel.host.registry import _principal_override

                principal = _principal_override.get()
            except Exception:
                principal = None
        if principal is None and ctx is not None:
            principal = getattr(ctx, "principal", None)
        uid = None
        if ctx is not None:
            uid = getattr(ctx, "subject", None) or getattr(ctx, "user_id", None)
            if not uid and getattr(ctx, "scope", None):
                uid = ctx.scope.get("user_id") or ctx.scope.get("subject") or ctx.scope.get("sub")
        uid = uid or kwargs.get("user_id") or kwargs.get("sub") or kwargs.get("subject")
        if principal is not None:
            uid = (
                uid
                or getattr(principal, "id", None)
                or getattr(principal, "sub", None)
                or (principal if isinstance(principal, str) else None)
            )
        return uid, ctx

    def _check(*args: Any, **kwargs: Any):
        uid, ctx = _resolve_uid(*args, **kwargs)
        if not uid:
            return None, ch.fail.auth()
        if ctx is not None and getattr(ctx, "scope", None) is not None:
            ctx.scope.setdefault("user_id", uid)
            ctx.scope.setdefault("subject", uid)
        return True, None

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            ok, denied = _check(*args, **kwargs)
            if denied is not None:
                return denied
            return await fn(*args, **kwargs)
    else:
        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            ok, denied = _check(*args, **kwargs)
            if denied is not None:
                return denied
            return fn(*args, **kwargs)

    try:
        wrapped.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    except Exception:
        pass
    return wrapped


def attach_flow(channel: Any) -> Flow:
    """Wire the stable product surface onto Channel."""
    flow = Flow(channel)
    book = channel.regions

    channel.flow = flow
    channel.fail = flow.fail
    channel.done = flow.done
    channel.refresh = flow.refresh  # region reload (overrides morph helper name)
    channel.notice = flow.notice
    channel.filter = flow.filter
    channel.draft = flow.draft

    # removed from product surface — keep only if tests still need via registry path
    # do NOT bind: ok, err, view, sync, notify, search

    channel.region = book.region
    channel.html = book.html
    channel.snapshot = book.snapshot

    def on(
        name: Any = None,
        *,
        refresh: Sequence[Any] = (),
        notice: Optional[str] = None,
        notice_level: str = "info",
        auth: bool = False,
        once: bool = False,
        idempotent: bool = False,
        roles: Sequence[str] = (),
        audit: bool = False,
        after: Sequence[Any] = (),
        toast: Optional[str] = None,
        login: bool = False,
        toast_level: str = "info",
    ):
        """
        Register an action.

        ::

            @ch.on(refresh=[cart_badge])     # name = function name
            def add(ctx, product_id: str): ...

            @ch.on                           # bare
            def ping(ctx): ...

            @ch.on("cart.add", refresh=[cart_badge])
            def add(...): ...
        """
        # @ch.on  (bare — name is the function)
        if callable(name) and not isinstance(name, str):
            fn = name
            return on(
                fn.__name__,
                refresh=refresh,
                notice=notice,
                notice_level=notice_level,
                auth=auth,
                once=once,
                idempotent=idempotent,
                roles=roles,
                audit=audit,
            )(fn)

        rev = resolve_uids(refresh) if refresh else resolve_uids(after)
        if toast is not None and notice is None:
            notice = toast
        if toast_level and notice_level == "info":
            notice_level = toast_level
        need_auth = auth or login
        role_list = tuple(roles or ())
        explicit_name = name if isinstance(name, str) else None

        def decorator(fn: Handler):
            import inspect
            from ux_channel.devtools.enterprise import ActionPolicy, require_roles

            action_name = explicit_name or fn.__name__

            if hasattr(channel, "policies"):
                channel.policies.set(
                    action_name,
                    ActionPolicy(once=once, roles=role_list, audit=audit),
                )

            def _finish(out: Any, *, notice=notice, notice_level=notice_level, rev=rev):
                if out is None:
                    return flow.done(notice, notice_level=notice_level)
                if isinstance(out, str) and (rev or notice):
                    return flow.done(out, notice_level=notice_level)
                return out

            if inspect.iscoroutinefunction(fn):
                async def user_fn(*args: Any, **kwargs: Any) -> Any:
                    ctx = kwargs.get("ctx")
                    scope = dict(getattr(ctx, "scope", None) or {})
                    principal = _principal_from_call(*args, **kwargs)
                    flow.push_refresh(rev, principal=principal, scope=scope)
                    try:
                        if role_list:
                            denied = require_roles(
                                channel, role_list, principal=principal, ctx=ctx
                            )
                            if denied is not None:
                                return denied
                        out = await fn(*args, **kwargs)
                        if audit and hasattr(channel, "audit"):
                            actor = None
                            if ctx is not None:
                                actor = getattr(ctx, "subject", None) or ctx.user_id
                            channel.audit(action_name, actor=actor, keys=dict(scope))
                        return _finish(out)
                    finally:
                        flow.clear_refresh()
            else:
                def user_fn(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
                    ctx = kwargs.get("ctx")
                    scope = dict(getattr(ctx, "scope", None) or {})
                    principal = _principal_from_call(*args, **kwargs)
                    flow.push_refresh(rev, principal=principal, scope=scope)
                    try:
                        if role_list:
                            denied = require_roles(
                                channel, role_list, principal=principal, ctx=ctx
                            )
                            if denied is not None:
                                return denied
                        out = fn(*args, **kwargs)
                        if audit and hasattr(channel, "audit"):
                            actor = None
                            if ctx is not None:
                                actor = getattr(ctx, "subject", None) or ctx.user_id
                            channel.audit(action_name, actor=actor, keys=dict(scope))
                        return _finish(out)
                    finally:
                        flow.clear_refresh()

            try:
                user_fn.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
            except Exception:
                pass
            user_fn.__name__ = getattr(fn, "__name__", action_name)
            user_fn.__doc__ = fn.__doc__
            if need_auth:
                user_fn = _auth_wrap(channel, user_fn)

            registered = book.command(
                action_name,
                revalidate=rev,
                toast=notice,
                toast_level=notice_level,
                login=False,
                once=once,
                idempotent=idempotent,
            )(user_fn)

            # stamp for demo_button(ch, fn) / refresh=[fn]
            target_fn = fn
            target_fn.action = action_name  # type: ignore[attr-defined]
            target_fn.refresh_uids = list(rev)  # type: ignore[attr-defined]
            target_fn.idempotent = bool(idempotent)  # type: ignore[attr-defined]
            registered.action = action_name  # type: ignore[attr-defined]
            registered.refresh_uids = list(rev)  # type: ignore[attr-defined]
            registered.idempotent = bool(idempotent)  # type: ignore[attr-defined]
            return registered

        return decorator

    channel.on = on
    return flow



# Closed public surface — stable long-term set
CHANNEL_PUBLIC = frozenset(
    {
        # lifecycle
        "boot",
        "from_registry",
        "diagnose",
        # regions + actions
        "region",
        "regions",
        "on",
        "use",
        "Region",
        "done",
        "fail",
        "html",
        "refresh",
        "patch",
        "notice",
        "filter",
        "draft",
        "snapshot",
        # UI protocol (minimal)
        "control",
        "runtime",
        "body_attrs",
        "wrap",
        # power / registry
        "action",
        "register",
        "mint",
        "before",
        "after",
        "registry",
        "config",
        "path",
        "state",
        "hub",
        "policies",
        "audit",
        "audit_log",
        "paginate",
        "redirect",
        "ui",
        "sel",
        "uid_attr",
        "flow",
    }
)


def apply_surface(channel: Any) -> None:
    """Ensure removed names are not on the instance dict."""
    for removed in (
        "command", "login_required", "revalidate",
        "form_ok", "form_fail", "fail_auth", "fail_forbidden",
        "invalid", "require_user", "draft_get", "draft_set", "draft_clear",
        "ok", "err", "search", "regions", "login",
        "document", "head", "shell", "bind", "do", "attrs", "patterns", "Think",
        # removed HTML façade (keep html = region SSR)
        "page", "scripts", "button", "link", "submit", "form",
        "body_attr_string",
    ):
        if removed in CHANNEL_PUBLIC:
            continue
        if removed in getattr(channel, "__dict__", {}):
            del channel.__dict__[removed]
        # flow may have set attributes - only instance

