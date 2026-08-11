"""
Regions — morphable SSR slots with stable identity.

RegionBook is the REGISTRY (ch.regions). A single slot is Region / @ch.region — not this class renamed.

First principles
----------------
Server-driven UI updates a **fragment** of the page, not the whole document.
A **region** is that fragment:

- Stable ``data-channel-id`` (e.g. ``Cart:badge``)
- Server can re-render HTML for that id
- Client applies a ``morph`` / ``swap`` op targeting ``[data-channel-id="…"]``

This is **not**:
- An npm widget host → that is a **bridge** (``mount_html``)
- A React component tree → Python returns HTML strings (or ux-dom objects)

RegionBook (``ch.regions``)
---------------------------
Also named **RegionBook** (alias) — same type. Prefer speech: "region registry".
``Region`` remains the type for **one** slot (not renamed).

Registry of uid → render function / Region instance. ``revalidate`` /
product speech **refresh** re-renders selected uids and returns morph ops.

Intended usage
--------------
::

    @ch.region
    def cart_badge(ctx):
        return f"<span>{count}</span>"

    @ch.on(refresh=[cart_badge])
    def add(...):
        ...

Class style::

    class Badge(Region):
        def render(self, ctx): ...
        @Region.action(refresh=True)
        def add(self, product_id: str): ...

See: docs/REGIONS.md, docs/COURSE.md.
"""


from __future__ import annotations

import functools

import logging

logger = logging.getLogger("ux_channel.host.regions")

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, Union

from ux_channel.render.html_safe import SafeHtml, esc
from ux_channel.protocol.types import Result


def _id_str(uid: Any) -> str:
    if isinstance(uid, str):
        return uid
    u = getattr(uid, "uid", None)
    if u is not None:
        return str(u)
    return str(uid)


Loader = Callable[["RegionContext"], Any]
Renderer = Callable[[Any, "RegionContext"], Any]  # str | SafeHtml
ETagFn = Callable[[Any, "RegionContext"], str]


@dataclass
class RegionContext:
    """
    Per-request context for region model + paint.

    * subject / actor — who is acting
    * scope — resource ids (cart_id, user_id, …)
    * draft — ephemeral UI state
    """

    principal: Any = None
    scope: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    channel: Any = None

    @property
    def user_id(self) -> Any:
        p = self.principal
        if p is None:
            return self.scope.get("user_id") or self.scope.get("sub") or self.scope.get("actor")
        return getattr(p, "sub", None) or getattr(p, "id", None) or p

    @property
    def subject(self) -> Any:
        """Stable authorized party id (primary)."""
        return self.user_id

    @property
    def actor(self) -> Any:
        """Who performed this action (defaults to subject)."""
        return self.user_id

    # ctx.scope removed — use ctx.scope

    @property
    def draft(self) -> Any:
        return self.state

    def key(self, name: str, default: Any = None) -> Any:
        return self.scope.get(name, default)

    def flash(self, message: str, *, level: str = "info", key: str = "app.flash") -> None:
        """Write app flash payload; pair with @ch.region(\"app.flash\")."""
        store = self.state
        if store is None and self.channel is not None:
            store = getattr(self.channel, "state", None)
        if store is None:
            return
        actor = self.subject or self.actor or "anon"
        store.set(f"flash:{actor}:{key}", {"message": message, "level": level})


@dataclass
class RegionDef:
    """One morphable region: stable uid + load + render."""

    uid: str
    load: Loader
    render: Renderer
    etag: Optional[ETagFn] = None
    description: str = ""

    def data(self, ctx: RegionContext) -> Any:
        return self.load(ctx)

    def html(self, ctx: RegionContext, *, data: Any = None) -> str:
        """Internal: model + render → str."""
        if data is None:
            data = self.data(ctx)
        out = self.render(data, ctx)
        if isinstance(out, SafeHtml):
            return str(out)
        if out is None:
            return ""
        return str(out)

    def fingerprint(self, ctx: RegionContext, *, data: Any = None) -> Optional[str]:
        if not self.etag:
            return None
        if data is None:
            data = self.data(ctx)
        return str(self.etag(data, ctx))


class RegionBook:
    """
    Registry of regions for a Channel.

    Attached as ``ch.regions``.
    """

    def __init__(self, channel: Any):
        self.channel = channel
        self._regions: dict[str, RegionDef] = {}

    def __contains__(self, uid: Any) -> bool:
        return _id_str(uid) in self._regions

    def get(self, uid: Any) -> RegionDef:
        uid = _id_str(uid)
        try:
            return self._regions[uid]
        except KeyError as exc:
            raise KeyError(f"unknown region {uid!r}; register with @ch.region") from exc

    def define(
        self,
        uid: str,
        *,
        load: Loader,
        render: Renderer,
        etag: Optional[ETagFn] = None,
        description: str = "",
    ) -> RegionDef:
        island = RegionDef(uid=uid, load=load, render=render, etag=etag, description=description)
        if uid in self._regions:
            logger.warning(
                "region_uid_overwrite uid=%s (last register wins)",
                uid,
            )
        self._regions[uid] = island
        return island

    def register(
        self,
        uid: Any = None,
        *,
        etag: Optional[ETagFn] = None,
        description: str = "",
    ):
        """
        Register a region (organic by default).

        ::

            @ch.region                    # uid from function name
            def cart_badge(ctx):
                return span(str(n))

            @ch.region("cart.badge")      # explicit uid
            def cart_badge(ctx):
                ...

            @ch.region(refresh?)          # not used — see @ch.on
        """

        def _auto_uid(fn: Any) -> str:
            name = getattr(fn, "__name__", "region")
            # cart_badge -> cart.badge (readable); keep if no underscore
            return name.replace("_", ".")

        def _register(fn: Loader, uid_s: str):
            def _paint_only(_data: Any, ctx: RegionContext) -> Any:
                return fn(ctx)

            def _load_identity(ctx: RegionContext) -> Any:
                return None

            isl = self.define(
                uid_s,
                load=_load_identity,
                render=_paint_only,
                etag=etag,
                description=description,
            )
            isl._organic = True  # type: ignore[attr-defined]
            isl._fn = fn  # type: ignore[attr-defined]

            def paint_decorator(render_fn: Renderer):
                isl.load = fn  # type: ignore[assignment]
                isl.render = render_fn
                isl._organic = False  # type: ignore[attr-defined]
                return fn

            fn.html = paint_decorator  # type: ignore[attr-defined]
            fn.paint = paint_decorator  # type: ignore[attr-defined]
            fn.uid = uid_s  # type: ignore[attr-defined]
            fn.island = isl  # type: ignore[attr-defined]
            fn.region = isl  # type: ignore[attr-defined]
            return fn

        # @ch.region  (bare)
        if callable(uid) and not isinstance(uid, str):
            fn = uid
            return _register(fn, _auto_uid(fn))

        # @ch.region() or @ch.region("id") or @ch.region(uid="id")
        explicit = uid if isinstance(uid, str) else None

        def decorator(fn: Loader):
            return _register(fn, explicit or _auto_uid(fn))

        return decorator

    # Public names
    region = register  # product name used by flow

    def context(
        self,
        *,
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        meta: Optional[Mapping[str, Any]] = None,
        **extra: Any,
    ) -> RegionContext:
        s = dict(scope or {})
        s.update(extra)
        return RegionContext(
            principal=principal,
            scope=s,
            state=getattr(self.channel, "state", None),
            meta=dict(meta or {}),
            channel=self.channel,
        )

    def html(
        self,
        uid: Union[str, Callable[..., Any]],
        *,
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        wrap: bool = True,
        **extra: Any,
    ) -> str:
        """SSR paint → str (for ``raw()`` / string hosts). Prefer nesting tags when possible."""
        uid = _id_str(uid)
        merged = dict(scope or {})
        merged.update(extra)
        ctx = self.context(principal=principal, scope=merged or None)
        body = self.get(uid).html(ctx)
        if not wrap:
            return body
        return self.channel.wrap(uid, body)

    def snapshot(
        self,
        *uids: str,
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        **extra: Any,
    ) -> dict[str, str]:
        """uid → html for many regions (SSR pages / multi morph)."""
        ctx = self.context(principal=principal, scope=scope, **extra)
        out: dict[str, str] = {}
        for uid in uids:
            uid = _id_str(uid)
            out[uid] = self.get(uid).html(ctx)
        return out

    def revalidate(
        self,
        *uids: str,
        principal: Any = None,
        scope: Optional[Mapping[str, Any]] = None,
        toast: Optional[str] = None,
        toast_level: str = "info",
        etags: Optional[Mapping[str, str]] = None,
        **extra: Any,
    ) -> Result:
        """
        Re-load regions from loaders and morph changed ones.

        **Product API:** ``ch.refresh(*uids)`` / ``ch.done(refresh=uids)``.
        RegionBook implementation (``ch.regions``).

        If ``etags`` provided (client/server prior fingerprint), skip morph when equal.
        """
        ctx = self.context(principal=principal, scope=scope, **extra)
        regions: dict[str, str] = {}
        missing: list[str] = []
        for uid in uids:
            uid = _id_str(uid)
            isl = self._regions.get(uid)
            if isl is None:
                # Do not raise → would surface as action "internal".
                # Skip + warn so partial refresh lists still apply known regions.
                missing.append(uid)
                continue
            try:
                data = isl.data(ctx)
                fp = isl.fingerprint(ctx, data=data)
                if etags and fp is not None and etags.get(uid) == fp:
                    continue
                regions[uid] = isl.html(ctx, data=data)
            except Exception as exc:  # noqa: BLE001
                # One broken region must not wipe the whole action as a bare
                # traceback-as-internal — skip + warn (same class as unknown uid).
                logger.exception("region_render_failed uid=%s", uid)
                missing.append(f"{uid}!(render:{type(exc).__name__})")
                continue
        if missing:
            logger.warning(
                "revalidate_unknown_regions missing=%s (skipped)",
                missing,
            )
        # Total failure: every requested uid missing or render-crashed → not silent ok.
        if not regions and not toast:
            if missing and uids:
                return Result.failure(
                    "render_error",
                    "region refresh failed or unknown: "
                    + ", ".join(str(m) for m in missing[:8]),
                    retryable=True,
                    refresh_errors=list(missing),
                )
            return Result.success()  # empty refresh list → true no-op
        if not regions and toast:
            # Total paint failure must not look like success ("Saved!" lie).
            # Fail closed; keep notice as a *warning* toast op so UX can still flash.
            from ux_channel.protocol.ops import toast as toast_op

            err_msg = (
                "region refresh failed or unknown: "
                + ", ".join(str(m) for m in missing[:8])
            )
            ops = [
                toast_op(toast, level="warning" if toast_level == "info" else toast_level),
            ]
            return Result.failure(
                "render_error",
                err_msg,
                *ops,
                retryable=True,
                refresh_errors=list(missing),
            )
        result = self.channel.patch(regions, notice=toast)
        if missing:
            meta = dict(result.meta or {})
            meta["refresh_errors"] = list(missing)
            return Result(
                v=result.v,
                ok=result.ok,
                ops=list(result.ops),
                error=result.error,
                meta=meta,
            )
        return result


    def command(
        self,
        name: str,
        *,
        revalidate: Sequence[str] = (),
        toast: Optional[str] = None,
        toast_level: str = "info",
        once: bool = False,
        login: bool = False,
        idempotent: bool = False,
    ):
        """
        Internal: register a mutation action that may revalidate regions.

        **Product API is** ``@ch.on(name, refresh=[...], ...)`` — do not teach
        ``RegionBook.command`` as the app-facing decorator.
        """

        def decorator(fn: Callable[..., Any]):
            import functools
            import inspect

            ch = self.channel
            if login:
                from ux_channel.host.flow import _auth_wrap

                fn = _auth_wrap(ch, fn)

            def _prepare_call(args, kwargs):
                """Build RegionContext from dispatch kwargs.

                Registry injects ``ctx=ActionContext`` (with soft/hard principal).
                That identity must not be discarded when we rebuild RegionContext —
                otherwise auth=True and multi-tenant scope silently see ``anon``.
                """
                principal = kwargs.pop("principal", None)
                scope = dict(kwargs.pop("scope", None) or {})
                # Registry-bound ActionContext carries principal + meta keys
                existing_ctx = kwargs.pop("ctx", None)
                if existing_ctx is not None:
                    if principal is None:
                        principal = getattr(existing_ctx, "principal", None)
                    meta = getattr(existing_ctx, "meta", None) or {}
                    if isinstance(meta, Mapping):
                        for k, v in meta.items():
                            if v is not None:
                                scope.setdefault(k, v)
                    # ActionContext.user_id / subject (properties)
                    uid_existing = getattr(existing_ctx, "user_id", None) or getattr(
                        existing_ctx, "subject", None
                    )
                    if uid_existing:
                        scope.setdefault("user_id", uid_existing)
                        scope.setdefault("subject", uid_existing)
                        scope.setdefault("sub", uid_existing)
                    # claims → scope (roles, tenant_id, …)
                    if principal is not None:
                        claims = getattr(principal, "claims", None) or {}
                        if isinstance(claims, Mapping):
                            for k, v in claims.items():
                                if v is not None and (
                                    k.endswith("_id")
                                    or k in ("roles", "role", "user_id", "sub", "subject", "tenant_id")
                                ):
                                    scope.setdefault(k, v)
                for k in list(kwargs.keys()):
                    if k in ("roles", "role"):
                        continue
                    if k.endswith("_id") or k in (
                        "id", "uid", "sub", "user_id", "subject", "tenant_id",
                    ):
                        scope.setdefault(k, kwargs[k])
                # Soft principal from ContextVar when still missing
                if principal is None:
                    try:
                        from ux_channel.host.registry import _principal_override

                        principal = _principal_override.get()
                    except Exception:
                        principal = None
                if principal is not None:
                    pid = (
                        getattr(principal, "id", None)
                        or getattr(principal, "sub", None)
                        or principal
                    )
                    scope.setdefault("user_id", pid)
                    scope.setdefault("subject", pid)
                    scope.setdefault("sub", pid)
                    if "roles" not in scope:
                        roles = (getattr(principal, "claims", None) or {}).get("roles")
                        if not roles:
                            roles = getattr(principal, "scopes", None)
                        if roles:
                            scope["roles"] = (
                                list(roles) if not isinstance(roles, str) else [roles]
                            )
                ctx = self.context(principal=principal, scope=scope)
                try:
                    sig = inspect.signature(fn)
                    params = sig.parameters
                    accepts_var_kw = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
                    )
                    call_kwargs = {}
                    for k, v in kwargs.items():
                        if k in params or accepts_var_kw:
                            call_kwargs[k] = v
                    if "ctx" in params:
                        call_kwargs["ctx"] = ctx
                    if "principal" in params and principal is not None:
                        call_kwargs["principal"] = principal
                except (TypeError, ValueError):
                    call_kwargs = dict(kwargs)
                    call_kwargs["ctx"] = ctx
                return args, call_kwargs, principal, scope

            def _coerce_out(out: Any, principal: Any, scope: dict) -> Any:
                if isinstance(out, Result):
                    return out
                rev = list(revalidate)
                tmsg = toast
                tlevel = toast_level
                princ = principal
                k2 = scope
                if isinstance(out, str):
                    tmsg = out
                elif isinstance(out, Mapping):
                    # Result wire shape — do NOT treat as refresh/toast config.
                    # Footgun: {"ok": False, "error": {...}} used to become ok Result.
                    if (
                        "ok" in out
                        and "op" not in out
                        and ("ops" in out or "error" in out)
                    ):
                        try:
                            return Result.from_dict(dict(out))  # type: ignore[arg-type]
                        except Exception:
                            pass  # fall through to config mapping
                    if "revalidate" in out:
                        rev = list(out["revalidate"])  # type: ignore[index]
                    if "toast" in out:
                        tmsg = out["toast"]  # type: ignore[index]
                    if "toast_level" in out:
                        tlevel = str(out["toast_level"])  # type: ignore[index]
                    if "principal" in out:
                        princ = out["principal"]
                    if "scope" in out:
                        k2 = dict(out["scope"])
                    elif "keys" in out:
                        k2 = dict(out["keys"])  # type: ignore[index]
                    if out.get("result") is not None:  # type: ignore[union-attr]
                        return out["result"]  # type: ignore[index]
                if not rev:
                    if tmsg:
                        return ch.ui.toast(tmsg, level=tlevel).ok()
                    return Result.success()
                return self.revalidate(
                    *rev,
                    principal=princ,
                    scope=k2,
                    toast=tmsg,
                    toast_level=tlevel,
                )

            if inspect.iscoroutinefunction(fn):
                @ch.registry.action(name, idempotent=idempotent)
                async def _wrapped(*args: Any, **kwargs: Any) -> Any:
                    args, call_kwargs, principal, scope = _prepare_call(args, kwargs)
                    out = await fn(*args, **call_kwargs)
                    return _coerce_out(out, principal, scope)
            else:
                @ch.registry.action(name, idempotent=idempotent)
                def _wrapped(*args: Any, **kwargs: Any) -> Any:
                    args, call_kwargs, principal, scope = _prepare_call(args, kwargs)
                    out = fn(*args, **call_kwargs)
                    # Propagate accidental awaitables (should not happen if fn is sync)
                    if inspect.isawaitable(out):
                        raise TypeError(
                            f"action {name!r} returned awaitable from sync handler; "
                            "declare the handler with async def"
                        )
                    return _coerce_out(out, principal, scope)

            functools.update_wrapper(_wrapped, fn)
            _wrapped.__name__ = getattr(fn, "__name__", name)
            try:
                _wrapped.__signature__ = inspect.signature(fn)
            except (TypeError, ValueError):
                pass
            return _wrapped

        return decorator

    def uids(self) -> list[str]:
        return list(self._regions.keys())


def attach_regions(channel: Any) -> RegionBook:
    """Attach RegionBook as ``ch.regions`` — product verbs come from flow.attach_flow."""
    existing = getattr(channel, "regions", None)
    if isinstance(existing, RegionBook):
        return existing
    book = RegionBook(channel)
    channel.regions = book
    return book

# Intent-aligned alias: "registry of regions" speech
RegionBook = RegionBook

