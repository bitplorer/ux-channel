"""Channel — the app-facing façade for ux-channel.

  ``draft`` / ``done`` / ``fail`` / ``webrtc`` / …
* Does **not** own HTML trees (ux-dom / templates do).
* Owns registration, capabilities, ephemeral draft, Results, live plane.

See ``Channel.describe()`` and docs/API_SURFACE.md."""


from __future__ import annotations

import logging

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, Union  # noqa: F401

from ux_channel.host.config import ChannelConfig
from ux_channel.protocol.navigate_markers import Go, Navigate
from ux_channel.host.factory import create_channel
from ux_channel.render.html import action_attrs
from ux_channel.render.html_safe import esc, user_content
from ux_channel.protocol.ops import (
    Op,
    clear_errors,
    dispatch as op_dispatch,
    focus,
    morph,
    navigate,
    push_url,
    reload,
    remove,
    scroll,
    set_attr,
    set_text,
    toast,
)
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Result

Handler = Callable[..., Any]


def sel(uid_id: str) -> str:
    """CSS selector for a stable region: ``[data-channel-id="Counter:root"]``."""
    if uid_id.startswith("[") or uid_id.startswith("#") or uid_id.startswith("."):
        return uid_id
    return f'[data-channel-id="{uid_id}"]'


def uid_attr(uid_id: str) -> str:
    """``data-channel-id="…"`` attribute fragment."""
    return f'data-channel-id="{esc(uid_id)}"'


@dataclass
class UiBuilder:
    """
    Fluent Result builder for the morph/toast/focus loop.

    Usage::

        return ch.ui.region("Cart:badge", badge_html()).toast("Added").ok()
        return ch.ui.fail_validation(fields, region="Login:root", html=form_html())
    """

    _ops: list[Op] = field(default_factory=list)
    _ok: bool = True
    _error_code: Optional[str] = None
    _error_message: Optional[str] = None
    _fields: Optional[dict[str, list[str]]] = None
    _meta: dict[str, Any] = field(default_factory=dict)

    def region(self, uid_id: str, html: str, *, mode: str = "idiomorph") -> "UiBuilder":
        self._ops.append(morph(target=sel(uid_id), html=html, morph=mode))
        return self

    def morph_target(self, target: str, html: str, *, mode: str = "idiomorph") -> "UiBuilder":
        self._ops.append(morph(target=target, html=html, morph=mode))
        return self

    def toast(self, message: str, *, level: str = "info") -> "UiBuilder":
        self._ops.append(toast(message, level=level))
        return self

    def focus(self, target: str, *, select: bool = False) -> "UiBuilder":
        self._ops.append(focus(target=target, select=select))
        return self

    def push_url(self, href: str) -> "UiBuilder":
        self._ops.append(push_url(href))
        return self

    def navigate(self, href: str, *, replace: bool = False) -> "UiBuilder":
        self._ops.append(navigate(href, replace=replace))
        return self

    def go(self, href: str) -> "UiBuilder":
        """Full navigation as the only outcome (encode path). Prefer ``ok`` after navigate."""
        self._ops.append(navigate(href))
        return self

    def remove(self, uid_id: str) -> "UiBuilder":
        self._ops.append(remove(target=sel(uid_id)))
        return self

    def set_text(self, uid_id: str, text: str) -> "UiBuilder":
        self._ops.append(set_text(target=sel(uid_id), text=text))
        return self

    def set_attr(self, uid_id: str, **attrs: Any) -> "UiBuilder":
        self._ops.append(set_attr(target=sel(uid_id), attrs=attrs))
        return self

    def clear_errors(self, uid_id: Optional[str] = None) -> "UiBuilder":
        self._ops.append(clear_errors(target=sel(uid_id) if uid_id else None))
        return self

    def scroll(self, target: Optional[str] = None, **kwargs: Any) -> "UiBuilder":
        self._ops.append(scroll(target=target, **kwargs))
        return self

    def dispatch_event(self, name: str, **kwargs: Any) -> "UiBuilder":
        self._ops.append(op_dispatch(name, **kwargs))
        return self

    def op(self, *ops: Op | Sequence[Op]) -> "UiBuilder":
        for item in ops:
            if isinstance(item, Mapping) and "op" in item:
                self._ops.append(dict(item))  # type: ignore[arg-type]
            elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                for sub in item:
                    self._ops.append(dict(sub))  # type: ignore[arg-type]
            else:
                self._ops.append(item)  # type: ignore[arg-type]
        return self

    def meta(self, **kwargs: Any) -> "UiBuilder":
        self._meta.update(kwargs)
        return self

    def ok(self, **meta: Any) -> Result:
        m = {**self._meta, **meta}
        return Result.success(*self._ops, **m)

    def fail(
        self,
        code: str,
        message: str,
        *,
        fields: Optional[dict[str, list[str]]] = None,
        retryable: Optional[bool] = None,
        **meta: Any,
    ) -> Result:
        m = {**self._meta, **meta}
        return Result.failure(
            code,
            message,
            *self._ops,
            fields=fields or self._fields,
            retryable=retryable,
            **m,
        )

    def fail_validation(
        self,
        fields: dict[str, list[str]],
        *,
        message: str = "Please fix the highlighted fields",
        region: Optional[str] = None,
        html: Optional[str] = None,
        focus_target: Optional[str] = None,
    ) -> Result:
        """Standard form failure: optional re-morph + focus + error toast."""
        b = UiBuilder(_ops=list(self._ops), _meta=dict(self._meta))
        if region is not None and html is not None:
            b.region(region, html)
        if focus_target:
            b.focus(focus_target, select=True)
        b.toast(message, level="error")
        return b.fail("validation", message, fields=fields)


# Public API architecture overview (keep small — decades of DX)
# Public API: boot → region → on → control → runtime → draft/done → media → bridge
# Power: webrtc, sign_*, live, flow, before/after, multi, diagnose, enterprise
# Demo HTML — ux_channel.render.kit only (not on Channel)
# Layers: webrtc / scaffold / sfu / otel — never grow root exports
CHANNEL_PUBLIC_API = (
    "boot",
    "on",
    "region",
    "control",
    "runtime",  # Placement: script URLs + client (no HTML)
    "draft",
    "done",
    "fail",
    "mint",  # CapService.mint — Rust-parity (not sign)
    "media",  # Placement bags — not HTML
    "bridge",  # widget mount_spec + ops — not HTML
    "config",
    "path",
)
# Power (not public API): refresh, diagnose, body_attrs, html, live, webrtc, patch, …
# Power layers (not public API): webrtc under ch.media

WEBRTC_PUBLIC_API = (
    "enabled",
    "path",
    "ws_path",
    "sign_ticket",
    "plugin",
    "ice",
    "body_attrs",
    "diagnose",
)


class Channel:
    """
    Application façade — **one object** for control + trust + regions.

    Construct only via ``Channel.boot`` (tests: ``from_registry``).

    Public API (learn only these)
    ------------------------
    ::

        ch = Channel.boot(app, config=ChannelConfig.development(...))

        @ch.region
        def badge(ctx):
            return f"<b>{ch.draft.get('n', 0)}</b>"

        @ch.on(refresh=[badge])
        def add():
            ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

        # markup: ch.control(add).as_dict() + ch.runtime().scripts (Placement)
        # media:  ch.media.plugin(room, sub=…)
        # bridge: ch.bridge.mount_spec + mount_ops / call

    | Call | Why |
    |------|-----|
    | ``boot`` | registry + mount + this façade |
    | ``region`` / ``on`` | morph slots + actions |
    | ``control`` | signed attrs for buttons/forms |
    | ``runtime`` | Placement — script URLs (no HTML) |
    | ``draft`` / ``done`` / ``fail`` / ``refresh`` | state + Result verbs |
    | ``media`` | mesh/SFU placement bags |
    | ``bridge`` | npm widget mount_spec + ops |

    Power (when you need them)
    --------------------------
    ``mint`` / ``sign_push`` / ``sign_ws``, ``live``, ``before``/``after``,
    ``multi``, ``patch``, ``flow``, ``diagnose``, ``audit*``, ``policies``.

    Demo only (not production UI kit)
    ---------------------------------
    HTML helpers live in ``ux_channel.render.kit`` only.
    Real apps: **ux-dom** (or Jinja) + ``control`` attrs only.

    Layers (import submodules)
    --------------------------
    ``ux_channel.scaffold``, ``.webrtc``, ``.sfu``, ``.whip``, ``.redis_extra``.
    """

    def __init__(
        self,
        registry: ActionRegistry,
        *,
        config: Any = None,
        hub: Any = None,
        path: str = "/ux-channel",
        state: Any = None,
    ):
        self.registry = registry
        self.config = config
        self.hub = hub
        self.path = path
        if state is not None:
            self.state = state
        else:
            from ux_channel.host.stores import MemoryStateStore

            # Dev-friendly default; production should pass redis-backed store
            self.state = MemoryStateStore()
        from ux_channel.host.regions import attach_regions
        from ux_channel.host.flow import apply_surface, attach_flow
        from ux_channel.host.region_component import attach_region_classes
        from ux_channel.render.html_document import attach_document
        from ux_channel.devtools.enterprise import attach_enterprise

        attach_regions(self)
        attach_enterprise(self)
        attach_flow(self)
        attach_region_classes(self)
        attach_document(self)
        apply_surface(self)
        from ux_channel.host.live import attach_live
        from ux_channel.realtime.webrtc import attach_webrtc
        from ux_channel.realtime.media import attach_media
        from ux_channel.bridge.bridge_plane import attach_bridge

        attach_live(self)
        attach_webrtc(self)
        attach_media(self)
        attach_bridge(self)
        from ux_channel.arch.attach import attach_arch

        attach_arch(self)

    # --- bootstrap ---------------------------------------------------------

    @classmethod
    def boot(
        cls,
        app: Any = None,
        *,
        secret: str | None = None,
        config: ChannelConfig | None = None,
        host: str = "fastapi",
        path: str = "/ux-channel",
        environment: str = "development",
        redis_url: str | None = None,
        require_cap: bool = True,
        state: Any = None,
        **kwargs: Any,
    ) -> "Channel":
        """
        One-call bootstrap: registry + mount + Channel façade.

        ::

            ch = Channel.boot(app, secret="dev-secret-key-32chars-minimum!!!!")
        """
        if config is None and secret is None:
            config = ChannelConfig.development()
        elif config is None and secret is not None and environment == "development":
            config = ChannelConfig.development(
                secret=secret,
                path=path,
                require_cap=require_cap,
            )
        if redis_url is None and config is not None:
            redis_url = getattr(config, "redis_url", None)
        reg, hub = create_channel(
            secret=secret,
            config=config,
            app=app,
            host=host if app is not None else None,
            path=path,
            environment=environment,
            redis_url=redis_url,
            require_cap=require_cap,
            **kwargs,
        )
        mount_path = getattr(config, "path", path) if config else path
        ch = cls(reg, config=config, hub=hub, path=mount_path, state=state)
        if state is None and redis_url:
            try:
                from ux_channel.redis_extra import RedisStateStore

                ch.state = RedisStateStore(redis_url)
            except Exception:
                logging.getLogger("ux_channel.boot").exception(
                    "RedisStateStore attach failed for redis_url — using default state"
                )
        # agents façade always available
        import logging as _logging
        _blog = _logging.getLogger("ux_channel.boot")
        try:
            from ux_channel.devtools.agents_api import agents as _agents

            _agents(ch)
        except Exception:
            _blog.exception("agents façade attach failed (non-fatal)")
        # audit trail when config.audit (production default)
        cfg = config
        if cfg is not None and getattr(cfg, "audit", False):
            try:
                from ux_channel.devtools.audit import attach_audit

                attach_audit(ch, redis_url=redis_url)
            except Exception:
                _blog.exception("audit attach failed — mutations may be unaudited")
        # opt-in file-based regions shell
        if cfg is not None and getattr(cfg, "regions", None):
            try:
                from ux_channel.host.region_directory import boot_load_regions

                boot_load_regions(ch, cfg)
            except Exception:
                # regions is explicit opt-in — fail closed if strict
                if getattr(cfg, "regions_strict", True):
                    raise
                _blog.exception("regions load failed (regions_strict=False)")
        else:
            try:
                from ux_channel.host.region_directory import attach_region_directory

                attach_region_directory(ch)
            except Exception:
                _blog.debug("region directory attach skipped", exc_info=True)
        # inspect helper (always bind; inspect_enabled gates use)
        try:
            from ux_channel.devtools.inspect_api import inspect_channel

            ch.inspect = lambda region=None, **kw: inspect_channel(  # type: ignore
                ch, region, **kw
            )
        except Exception:
            _blog.exception("inspect helper bind failed")
        # Optional enhancement plane (handshake / continuations / recorder)
        try:
            if cfg is None or getattr(cfg, "enhance", True) is not False:
                from ux_channel.enhance.attach import attach_enhance

                attach_enhance(ch)
                try:
                    ch.registry.channel = ch  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            _blog.exception("enhance plane attach failed (non-fatal)")
        return ch


    @classmethod
    def describe(cls) -> str:
        """One source of truth: control plane data — not HTML, not alias soup."""
        return (
            "uxchannel — one truth\n"
            "=======================\n"
            "Channel owns: actions, caps, regions, Result ops, placement DATA\n"
            "You own: all HTML (ux-dom / templates / React)\n"
            "\n"
            "Public API\n"
            "  boot → @region → @on → control → runtime → draft/done\n"
            "  media.plugin → Placement (attrs, client, scripts[])\n"
            "  bridge.mount_spec → Placement + mount_ops (widgets only)\n"
            "\n"
            "Never the source of truth\n"
            "  ch.scripts/page/button HTML strings → ux_channel.render.kit only\n"
            "  ch.webrtc → power layer under ch.media (mesh)\n"
            "  ch.bridge.media → removed; use ch.media\n"
            "\n"
            "Tools: Channel.help() · uxchannel create-app · doctor\n"
        )

    @classmethod
    def public_api_names(cls) -> tuple[str, ...]:
        """Application façade verbs (boot/on/region/control/…).

        Not every name is a bare class attribute — many bind on the
        instance after ``boot`` (e.g. ``on``, ``region``, ``runtime``).
        """
        return CHANNEL_PUBLIC_API

    def doctor(self) -> dict[str, Any]:
        """Health check: diagnose + actionable hints."""
        d = self.diagnose()
        hints: list[str] = []
        cfg = self.config
        env = getattr(cfg, "environment", None) if cfg else None
        if env == "production":
            if getattr(cfg, "allow_memory_stores", False):
                hints.append("production + allow_memory_stores: use Redis for multi-worker")
            if not getattr(cfg, "require_cap", True):
                hints.append("require_cap=False weakens action integrity")
            if not getattr(cfg, "webrtc_require_ticket", False):
                hints.append("enable webrtc_require_ticket for private media rooms")
        else:
            hints.append("development defaults: fine for local; use production() for deploy")
        media = d.get("media") or {}
        mode = media.get("default_mode")
        if mode == "mesh":
            hints.append("media=mesh — set sfu_provider=livekit for multiparty A/V")
        elif mode == "sfu":
            hints.append("media=sfu — ch.media.plugin(); host owns <video> elements")
        regions = d.get("regions") or []
        return {
            "ok": True,
            "environment": env,
            "path": self.path,
            "regions": len(regions) if isinstance(regions, list) else regions,
            "media_mode": mode,
            "public_api": list(CHANNEL_PUBLIC_API),
            "diagnose": d,
            "hints": hints,
            "next": [
                "uxchannel create-app myapp --template minimal",
                "uxchannel create-app call --template media",
                "print(Channel.help())",
                "uxchannel recipe --tree",
            ],
        }


    @classmethod
    def help(cls, topic: str | None = None) -> str:
        """
        Progressive disclosure help.

        * ``Channel.help()`` — decision tree
        * ``Channel.help("counter")`` — named recipe
        * ``Channel.help("aliases")`` — use-this-not-that
        * ``Channel.help("public_api")`` — architecture overview
        """
        from ux_channel.host.patterns import RECIPE_NAMES, decision_tree, recipe_text

        if not topic:
            return decision_tree() + "\nRecipes: " + ", ".join(RECIPE_NAMES)
        key = topic.strip().lower().replace("_", "-")
        if key in ("public_api", "describe", "architecture", "overview"):
            return cls.describe()
        if key in ("alias", "aliases", "rename", "prefer", "codec"):
            return (
                "Product speech (use these)\n"
                "---------------------------\n"
                "  ch.done / ch.fail.* / ch.control / ch.runtime\n"
                "  ch.media.plugin / ch.bridge.mount_spec\n"
                "  notice=  go=  scope=  trust_*\n"
                "  ux_channel.render.kit for markup strings\n"
                "\n"
                "Wire (not app speech)\n"
                "--------------------\n"
                "  Result.success / Result.failure\n"
                "  op toast ← notice | op navigate ← go\n"
                "  data-channel-* from control / body_attrs / Placement\n"
            )
        if key in ("doctor", "health"):
            return "Boot a Channel and call ch.doctor() — or: uxchannel doctor"
        if key in ("bridge", "bridges", "npm", "preset"):
            from ux_channel.bridge.bridge_scaffold import explain_bridge
            return explain_bridge()
        if key in RECIPE_NAMES:
            return recipe_text(key)
        return (
            f"Unknown topic {topic!r}.\n\n"
            + decision_tree()
            + "\nRecipes: "
            + ", ".join(RECIPE_NAMES)
        )

    def explain(self, result_or_code: Any, message: str = "") -> dict[str, Any]:
        """Map a Result/error code to a teachable fix + recipe link."""
        from ux_channel.devtools.explain import explain as _explain

        return _explain(result_or_code, message)

    def diagnose(self) -> dict[str, Any]:
        """Low-noise health snapshot for DX (no secrets)."""
        cfg = self.config
        book = getattr(self, "regions", None)
        return {
            "path": self.path,  # mount prefix, e.g. /ux-channel (action URL is path + "/action")
            "action_endpoint": f"{str(self.path).rstrip('/')}/action",
            "actions": len(getattr(self.registry, "_actions", {}) or {}),
            "regions": list(book.uids()) if book else [],
            "require_cap": getattr(self.registry, "require_cap", None),
            "environment": getattr(cfg, "environment", None) if cfg else None,
            "allow_memory_stores": getattr(cfg, "allow_memory_stores", None) if cfg else None,
            "observe": getattr(cfg, "observe", None) if cfg else None,
            "state": type(self.state).__name__,
            "live_bindings": getattr(getattr(self, "live", None), "bindings", lambda: {})(),
            "webrtc": (lambda w: w.diagnose() if w is not None else {})(getattr(self, "webrtc", None)),
            "media": (lambda m: m.diagnose() if m is not None else {})(getattr(self, "media", None)),
            "bridge": (lambda b: b.diagnose() if b is not None else {})(getattr(self, "bridge", None)),
            "otel": __import__("ux_channel.devtools.otel", fromlist=["status"]).status(),
            "presence": getattr(getattr(self, "live", None), "presence_snapshot", lambda: {})(),
            "effects": getattr(cfg, "effects", None) if cfg else None,
            "proofs": getattr(cfg, "proofs", None) if cfg else None,
            "flow": getattr(cfg, "flow", None) if cfg else None,
            "once_jti_enforced": getattr(self.registry, "nonce_store", None) is not None,
            "proofs_configured": getattr(self, "proofs", None) is not None,
        }

    @classmethod
    def from_registry(cls, registry: ActionRegistry, **kwargs: Any) -> "Channel":
        return cls(registry, **kwargs)

    # --- concurrency (first-class) ----------------------------------------

    def dispatch_parallel(
        self,
        intents: Any,
        *,
        max_workers: int | None = None,
        principal: Any = None,
        parallel: bool | None = None,
    ) -> list:
        """Parallel sync dispatch — see :func:`ux_channel.concurrency.dispatch_parallel`."""
        from ux_channel.transport.concurrency import dispatch_parallel

        return dispatch_parallel(
            self.registry,
            intents,
            max_workers=max_workers,
            principal=principal,
            parallel=parallel,
        )

    async def dispatch_parallel_async(
        self,
        intents: Any,
        *,
        limit: int | None = None,
        principal: Any = None,
        parallel: bool | None = None,
    ) -> list:
        """Concurrent async dispatch — see :func:`ux_channel.concurrency.dispatch_parallel_async`."""
        from ux_channel.transport.concurrency import dispatch_parallel_async

        return await dispatch_parallel_async(
            self.registry,
            intents,
            limit=limit,
            principal=principal,
            parallel=parallel,
        )

    def map_dispatch(
        self,
        action: str,
        args_list: Any,
        *,
        max_workers: int | None = None,
        principal: Any = None,
        parallel: bool | None = None,
    ) -> list:
        """Map one action over many arg dicts in parallel."""
        from ux_channel.transport.concurrency import map_dispatch

        return map_dispatch(
            self.registry,
            action,
            args_list,
            max_workers=max_workers,
            principal=principal,
            parallel=parallel,
        )


    # --- registry passthrough ----------------------------------------------

    def action(self, name: str, **kwargs: Any) -> Callable[[Handler], Handler]:
        """
        Low-level registry decorator (``@reg.action``).

        **Prefer** ``@ch.on`` / ``@Region.action`` for app code — those wire
        refresh, auth, and flow. Kept for advanced/registry-only registration.
        """
        return self.registry.action(name, **kwargs)

    def register(self, name: str, fn: Handler, **kwargs: Any) -> Handler:
        self.registry.register(name, fn, **kwargs)
        return fn

    def mint(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        return self.registry.mint(action, dict(args or {}), **kwargs)

    def sign_push(
        self,
        topic: str,
        *,
        sub: Optional[str] = None,
        max_age: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Mint short-lived SSE subscribe ticket for ``topic`` (production push auth)."""
        from ux_channel.security.push_security import sign_push_ticket

        cfg = self.config
        if cfg is None:
            raise RuntimeError("Channel.sign_push requires config (Channel.boot with config=)")
        return sign_push_ticket(cfg, topic, sub=sub, max_age=max_age, **kwargs)

    def sign_ws(
        self,
        topic: str,
        *,
        sub: Optional[str] = None,
        max_age: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Alias of ``sign_push`` — same ticket authorizes SSE and WebSocket."""
        return self.sign_push(topic, sub=sub, max_age=max_age, **kwargs)

    def revoke_ticket(self, ticket: str, *, ttl_s: float | None = None) -> None:
        """Revoke a push/WS ticket (logout / ban)."""
        from ux_channel.devtools.ticket_revoke import get_revocation_list

        age = ttl_s
        if age is None and self.config is not None:
            age = float(getattr(self.config, "push_ticket_max_age", 300) or 300)
        get_revocation_list().revoke(ticket, ttl_s=float(age or 300))

    def security_events(self, n: int = 50, *, kind: str | None = None) -> list:
        """Recent security events (cap fail, origin, rate, ticket…)."""
        from ux_channel.security.security_events import get_security_bus

        return get_security_bus().recent(n, kind=kind)

    def before(self, fn: Handler) -> Handler:
        self.registry.before(fn)
        return fn

    def after(self, fn: Handler) -> Handler:
        self.registry.after(fn)
        return fn

    # --- HTML / control helpers --------------------------------------------

    @staticmethod
    def sel(uid_id: str) -> str:
        return sel(uid_id)

    @staticmethod
    def uid_attr(uid_id: str) -> str:
        return uid_attr(uid_id)

    @staticmethod
    def _trusted_params(
        trust: Optional[Mapping[str, Any]] = None,
        **field_kw: Any,
    ) -> dict[str, Any]:
        """
        Collect **trusted** (immutable) parameters sealed into the capability.

        * ``trust={...}`` — dict form
        * ``trust_sku=...`` — field form (``trust_<name>``)

        Wire: intent ``args`` / ``data-channel-args`` (protocol name, not product API).
        """
        sealed: dict[str, Any] = dict(trust or {})
        for k, v in field_kw.items():
            if k.startswith("trust_") and len(k) > 6:
                sealed[k[6:]] = v
            else:
                raise TypeError(
                    f"unexpected keyword {k!r}; use trust={{...}} or trust_<field>=..."
                )
        return sealed

    def _protocol_attrs(
        self,
        action: Any,
        *,
        trust: Optional[Mapping[str, Any]] = None,
        target: Optional[str] = None,
        cap: Optional[str] = None,
        mint_cap: bool = True,
        sub: Optional[str] = None,
        once: bool = False,
        scopes: Optional[Sequence[str]] = None,
        extra: Optional[Mapping[str, str]] = None,
        **trust_fields: Any,
    ) -> Any:
        """Low-level protocol attrs. Prefer :meth:`control`."""
        from ux_channel.render.html import ControlAttrs

        sealed = self._trusted_params(trust, **trust_fields)
        action_name, target = self._resolve_action_target(action, target)
        tgt = sel(target) if target and not str(target).startswith(("[", "#", ".")) else target
        if cap is None and mint_cap:
            cap = self.registry.mint(
                action_name, sealed, sub=sub, once=once, scopes=list(scopes) if scopes else None
            )
        return ControlAttrs(action=action_name, trust=sealed, cap=cap, target=tgt, extra=extra)

    def control(
        self,
        action: Any,
        *,
        trust: Optional[Mapping[str, Any]] = None,
        target: Optional[str] = None,
        cap: Optional[str] = None,
        mint_cap: bool = True,
        sub: Optional[str] = None,
        once: bool = False,
        scopes: Optional[Sequence[str]] = None,
        extra: Optional[Mapping[str, str]] = None,
        **trust_fields: Any,
    ) -> Any:
        """
        Wire **your** UI control to a channel action (attrs only, no widget).

        ::

            button("Add", **ch.control(add_item, trust_sku=sku).as_ux_dom())
            button("Save", **ch.control(save).as_dict())
        """
        return self._protocol_attrs(
            action,
            trust=trust,
            target=target,
            cap=cap,
            mint_cap=mint_cap,
            sub=sub,
            once=once,
            scopes=scopes,
            extra=extra,
            **trust_fields,
        )


    def _resolve_action_target(
        self, action: Any, target: Optional[str]
    ) -> tuple[str, Optional[str]]:
        if callable(action) and not isinstance(action, str):
            action_name = getattr(action, "action", None) or getattr(action, "__name__", None)
            if not action_name:
                raise TypeError("action function has no name / .action stamp")
            if target is None:
                ru = getattr(action, "refresh_uids", None) or ()
                if len(ru) == 1:
                    target = ru[0] if ru else None  # type: ignore[misc]
            return str(action_name), target
        return str(action), target


    @property
    def ui(self) -> UiBuilder:
        """Fresh fluent Result builder."""
        return UiBuilder()

    def patch(
        self,
        uid_id: str | Mapping[str, str],
        html: str | None = None,
        *extra_ops: Op,
        notice: Optional[str] = None,
        notice_level: str = "info",
    ) -> Result:
        """
        Morph explicit HTML into region(s).

        * ``ch.patch(uid, html)`` — one region
        * ``ch.patch({uid: html, ...})`` — many regions (replaces multi)
        """
        if isinstance(uid_id, Mapping):
            if html is not None:
                raise TypeError("ch.patch(mapping) does not take a second html argument")
            regions = uid_id
            b = self.ui
            for rid, h0 in regions.items():
                h = str(h0)
                marker = f'data-channel-id="{rid}"'
                marker2 = f"data-channel-id='{rid}'"
                if marker not in h and marker2 not in h:
                    h = self.wrap(str(rid), h)
                b.region(rid, h)
            for op in extra_ops:
                b.op(op)
            if notice:
                b.toast(notice, level=notice_level)
            return b.ok()
        if html is None:
            raise TypeError("ch.patch(uid, html) requires html")
        b = self.ui.region(str(uid_id), html)
        for op in extra_ops:
            b.op(op)
        if notice:
            b.toast(notice, level=notice_level)
        return b.ok()

    def redirect(self, href: str) -> Union[Go, Result]:
        """Full-page navigation after success (Login → /app)."""
        return Go(href)


    def wrap(self, uid_id: str, inner: str, *, tag: str = "div", **attrs: str) -> str:
        """Wrap content in a stable ``data-channel-id`` root."""
        extra = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
        return f'<{tag} {uid_attr(uid_id)}{(" " + extra) if extra else ""}>{inner}</{tag}>'


# Short alias for fluent builder
UI = UiBuilder