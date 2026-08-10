"""
Class-style Region components — ux-dom-adjacent, low ceremony.

Region is ONE slot. RegionBook (in regions.py) is the registry of all slots — different type, not a rename.

First principles
----------------
* A **Region** is a live DOM slot with a stable ``uid``.
* An **action** is a method that mutates truth/draft and refreshes region(s).
* Mounting is what *registers* model + actions with the Channel.
* The controlled region is always explicit: default = **this** instance's uid;
  override with ``@Region.action(refresh=[other])`` or ``refresh=False``.

Usage (preferred)::

    class CartBadge(Region):
        def render(self, ctx):
            n = self.ch.draft.get("n", 0)
            return f"<strong>{n}</strong>"

        @Region.action                 # refreshes this region
        def add(self, product_id: str = "sku"):
            self.ch.draft.set("n", self.ch.draft.get("n", 0) + 1)

    badge = CartBadge(ch).mount()
    return demo_page(ch, badge, demo_button(ch, "Add", badge.add, trust_product_id="sku"))  # or ux-dom

Also::

    badge = ch.use(CartBadge)          # same as CartBadge(ch).mount()
    @Region.action(refresh=[Header])   # refresh another class/instance/uid
    @Region.action(name="cart.add")    # explicit wire name
"""

from __future__ import annotations

import inspect
import logging
import re
from typing import Any, Callable, Optional, Sequence, Union

Handler = Callable[..., Any]
log = logging.getLogger("ux_channel.region")


def class_to_uid(cls_or_name: Any) -> str:
    """CartBadge -> cart.badge; Already.dotted -> already.dotted."""
    name = cls_or_name if isinstance(cls_or_name, str) else getattr(cls_or_name, "__name__", "region")
    if "." in name and name == name.lower():
        return name
    # CamelCase / snake → dotted lower
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1.\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1.\2", s1)
    return s2.replace("_", ".").lower().strip(".")


def _resolve_refresh_spec(
    owner: "Region",
    refresh: Any,
) -> list[str]:
    """
    Decide which region uids an action refreshes.

    refresh=
      True / None  → [owner.uid]   (this component)
      False / ()   → []
      str          → [str]
      Region class → [class uid]
      Region inst  → [inst.uid]
      region fn    → [fn.uid]
      sequence     → map each
    """
    if refresh is False:
        return []
    if refresh is True or refresh is None:
        return [str(owner.uid)]
    if isinstance(refresh, str):
        return [refresh]
    if isinstance(refresh, type) and issubclass(refresh, Region):
        return [refresh.default_uid()]
    if isinstance(refresh, Region):
        return [str(refresh.uid)]
    if callable(refresh) and getattr(refresh, "uid", None):
        return [str(refresh.uid)]
    if isinstance(refresh, (list, tuple)):
        out: list[str] = []
        for item in refresh:
            if item is True:
                out.append(str(owner.uid))
            else:
                out.extend(_resolve_refresh_spec(owner, item))
        return out
    raise TypeError(f"cannot resolve refresh target: {refresh!r}")


def action(
    fn: Optional[Handler] = None,
    *,
    refresh: Any = True,
    name: Optional[str] = None,
    auth: bool = False,
    once: bool = False,
    roles: Sequence[str] = (),
    audit: bool = False,
    notice: Optional[str] = None,
    broadcast: Any = None,
    summary: Optional[str] = None,
    ax: bool = True,
):
    """
    Mark a Region method as a channel action.

    Default ``refresh=True`` → re-render **this** region after the method runs.
    ``ax=True`` (default) exposes the action on ``agents.tools_for``.
    """

    def decorator(method: Handler) -> Handler:
        method._ux_region_action = {  # type: ignore[attr-defined]
            "refresh": refresh,
            "name": name,
            "auth": auth,
            "once": once,
            "roles": tuple(roles or ()),
            "audit": audit,
            "notice": notice,
            "broadcast": broadcast,
            "summary": summary,
            "ax": bool(ax),
        }
        return method

    if fn is not None:
        return decorator(fn)
    return decorator


class Region:
    """
    Class-style morphable region + optional action methods.

    Subclass, implement ``render(self, ctx)``, decorate mutations with
    ``@Region.action``, then ``.mount()`` (or ``ch.use(Cls)``).
    """

    #: Override wire uid; default from class name (CartBadge → cart.badge)
    uid: str | None = None

    #: Optional human description for diagnose / docs
    description: str = ""

    #: Soft AX/control scopes (optional; not a security boundary alone)
    scopes: tuple[str, ...] = ()

    #: If True and loaded via RegionDirectory, auto-mount once (opt-in)
    singleton: bool = False

    #: Discovery: set False on abstract bases / mixins that subclass Region
    __region__: bool = True

    # expose decorator on the class for nice syntax: @Region.action
    action = staticmethod(action)

    def __init__(
        self,
        channel: Any = None,
        *,
        uid: Optional[str] = None,
        **scope: Any,
    ) -> None:
        self.ch = channel
        self.uid = uid or type(self).default_uid()
        self.scope = dict(scope)
        self._mounted = False
        # bound action callables after mount: name -> bound method stamped for button()
        self._actions: dict[str, Any] = {}
        # Wave 2/3: topics to fan-out after actions (set via broadcast_on or action kw)
        self._broadcast_topics: list[str] = []

    @classmethod
    def default_uid(cls) -> str:
        if cls.uid:
            return str(cls.uid)
        return class_to_uid(cls)

    # --- paint -------------------------------------------------------------

    def render(self, ctx: Any) -> Any:
        """Return markup (str / ux-dom / SafeHtml). Override this."""
        raise NotImplementedError(f"{type(self).__name__}.render(ctx) not implemented")

    def __call__(self, ctx: Any = None, **scope: Any) -> str:
        """
        SSR string paint — same as ``.html(**scope)``.

        ::

            badge()                      # str
            badge(order_id="ord-1")      # scope kwargs
            raw(badge())                 # ux-dom string path
        """
        merged = dict(scope)
        if ctx is not None:
            # allow badge(ctx) or badge(ctx, order_id=...)
            if not hasattr(ctx, "scope") and not hasattr(ctx, "principal"):
                # first positional was not a context — treat as error-free no-op
                pass
            else:
                merged = {**(getattr(ctx, "scope", None) or {}), **merged}
        return self.html(**merged)

    # --- region-owned state (Wave 3) ---------------------------------------

    @property
    def state_key(self) -> str:
        """Draft/state namespace for this region instance."""
        return f"region:{self.uid}"

    def state_get(self, key: str = "value", default: Any = None) -> Any:
        """Read namespaced draft value (``region:{uid}:{key}``)."""
        if self.ch is None:
            return default
        blob = self.ch.draft.get(self.state_key)
        if not isinstance(blob, dict):
            return default
        return blob.get(key, default)

    def state_set(self, key: str, value: Any) -> None:
        if self.ch is None:
            raise RuntimeError("Region not bound to a Channel")
        blob = self.ch.draft.get(self.state_key)
        if not isinstance(blob, dict):
            blob = {}
        else:
            blob = dict(blob)
        blob[key] = value
        self.ch.draft.set(self.state_key, blob)

    def state_change(self, key: str, mutator: Any, *, default: Any = None) -> Any:
        cur = self.state_get(key, default)
        nxt = mutator(cur)
        self.state_set(key, nxt)
        return nxt

    def broadcast_on(self, *topics: str) -> "Region":
        """After actions, publish these live topics (multi-tab fan-out)."""
        for t in topics:
            if t and t not in self._broadcast_topics:
                self._broadcast_topics.append(t)
        return self

    def _fanout_broadcast(self, refresh_uids: list[str]) -> None:
        topics = list(self._broadcast_topics)
        if not topics or self.ch is None:
            return
        live = getattr(self.ch, "live", None)
        for topic in topics:
            try:
                if live is not None:
                    live.publish(topic, *refresh_uids)
                else:
                    from ux_channel.transport.push import get_push_bus

                    get_push_bus().publish(topic, self.ch.refresh(*refresh_uids))
            except Exception:
                log.warning(
                    "region push publish failed topic=%s region=%s",
                    topic,
                    getattr(self, "uid", None),
                    exc_info=True,
                )


    # --- lifecycle ---------------------------------------------------------

    def mount(self, channel: Any = None) -> "Region":
        """
        Register this region + all ``@Region.action`` methods on the channel.

        Idempotent: second mount is a no-op.
        """
        if channel is not None:
            self.ch = channel
        if self.ch is None:
            raise RuntimeError(f"{type(self).__name__}.mount() needs a Channel")
        if self._mounted:
            return self

        ch = self.ch
        owner = self
        uid = self.uid

        # Organic-style region: paint calls instance.render
        @ch.region(uid)
        def _paint(ctx: Any) -> Any:
            # merge default scope into ctx.scope if empty keys for those
            if owner.scope:
                for k, v in owner.scope.items():
                    ctx.scope.setdefault(k, v)
            return owner.render(ctx)

        # keep handle for debugging
        self._paint_fn = _paint  # type: ignore[attr-defined]
        # instance acts like region fn for refresh
        # (Region already has .uid)

        # Register action methods
        for name, member in inspect.getmembers(type(self), predicate=inspect.isfunction):
            meta = getattr(member, "_ux_region_action", None)
            if not meta:
                continue
            self._register_action(name, member, meta)

        self._mounted = True
        return self

    def _register_action(self, method_name: str, unbound: Handler, meta: dict[str, Any]) -> None:
        ch = self.ch
        owner = self
        wire_base = str(owner.uid).replace(":", ".")
        action_name = meta.get("name") or f"{wire_base}.{method_name}"
        # Default wire name is uid.method so multiple instances of the same
        # Region class can mount without "action already registered".
        rev = _resolve_refresh_spec(owner, meta.get("refresh", True))

        # Bind method to instance
        bound = unbound.__get__(owner, type(owner))

        def handler(*args: Any, **kwargs: Any) -> Any:
            # drop ctx injection if method doesn't accept it
            try:
                sig = inspect.signature(bound)
                if "ctx" not in sig.parameters:
                    kwargs.pop("ctx", None)
                if "principal" not in sig.parameters:
                    kwargs.pop("principal", None)
            except (TypeError, ValueError):
                kwargs.pop("ctx", None)
                kwargs.pop("principal", None)
            out = bound(*args, **kwargs)
            # Wave 2/3: live fan-out for multi-tab
            bcast = meta.get("broadcast")
            topics: list[str] = []
            if bcast:
                if isinstance(bcast, str):
                    topics = [bcast]
                elif isinstance(bcast, (list, tuple)):
                    topics = [str(x) for x in bcast]
            topics = topics or list(owner._broadcast_topics)
            if topics:
                live = getattr(owner.ch, "live", None)
                for topic in topics:
                    try:
                        if live is not None:
                            live.publish(topic, *rev)
                        else:
                            from ux_channel.transport.push import get_push_bus

                            get_push_bus().publish(topic, owner.ch.refresh(*rev))
                    except Exception:
                        log.warning(
                            "region action push failed topic=%s action=%s",
                            topic,
                            action_name,
                            exc_info=True,
                        )
            return out

        # Register via product @ch.on — replace if remounting same wire name
        reg = ch.registry
        if action_name in getattr(reg, "_actions", {}):
            prev = reg.action_meta(action_name)
            prev_uid = prev.get("region_uid")
            strict = True
            cfg = getattr(ch, "config", None)
            if cfg is not None:
                strict = bool(getattr(cfg, "strict_action_names", True))
            if prev_uid and prev_uid != owner.uid and strict:
                raise ValueError(
                    f"action wire {action_name!r} already bound to region "
                    f"{prev_uid!r}; cannot bind {owner.uid!r} "
                    f"(set strict_action_names=False to override)"
                )
            try:
                del ch.registry._actions[action_name]
                ch.registry._action_meta.pop(action_name, None)
            except KeyError:
                pass
        deco = ch.on(
            action_name,
            refresh=rev,
            notice=meta.get("notice"),
            auth=bool(meta.get("auth")),
            once=bool(meta.get("once")),
            roles=meta.get("roles") or (),
            audit=bool(meta.get("audit")),
        )
        registered = deco(handler)
        summary = meta.get("summary")
        if not summary:
            summary = (inspect.getdoc(unbound) or "").strip().split(chr(10))[0] or None
        scopes = tuple(getattr(type(owner), "scopes", ()) or ())
        try:
            reg.update_action_meta(
                action_name,
                roles=list(meta.get("roles") or ()),
                summary=summary,
                ax=bool(meta.get("ax", True)),
                region_uid=str(owner.uid),
                scopes=list(scopes),
                method=method_name,
            )
        except Exception:
            log.exception(
                "update_action_meta failed action=%s region=%s — tools_for may miss metadata",
                action_name,
                owner.uid,
            )

        # Wrapper object stampable for control / demo_button
        def public_action(*args: Any, **kwargs: Any) -> Any:
            return bound(*args, **kwargs)

        public_action.action = action_name  # type: ignore[attr-defined]
        public_action.refresh_uids = list(rev)  # type: ignore[attr-defined]
        public_action.__name__ = method_name  # type: ignore[attr-defined]
        public_action.__doc__ = unbound.__doc__
        public_action._bound = bound  # type: ignore[attr-defined]
        registered.action = action_name  # type: ignore[attr-defined]
        registered.refresh_uids = list(rev)  # type: ignore[attr-defined]

        setattr(owner, method_name, public_action)
        owner._actions[action_name] = public_action

    # --- helpers for page / controls ---------------------------------------

    def html(self, **scope: Any) -> str:
        """SSR paint this region → **str** (mounted). ``badge()`` is the same."""
        if not self._mounted:
            self.mount()
        merged = {**self.scope, **scope}
        return self.ch.html(self.uid, scope=merged or None)

    def facts(self, principal: Any = None) -> dict[str, Any]:
        """Optional principal-safe facts for situation/inspect (override)."""
        return {}

    @classmethod
    def make(cls, channel: Any, key: str, **kw: Any) -> "Region":
        """Keyed instance: uid = ``{base}:{key}`` (key must not contain ':')."""
        if ":" in str(key):
            raise ValueError("region instance key must not contain ':'")
        base = cls.default_uid()
        return cls(channel, uid=f"{base}:{key}", **kw).mount()

    def control(self, method: Union[str, Handler], **kwargs: Any) -> Any:
        """
        Protocol attrs for one of this region's actions (no UI)::

            ux_dom_button("Add", **badge.control("add", trust_product_id=...).as_dict())
        """
        if isinstance(method, str):
            fn = getattr(self, method)
        else:
            fn = method
        return self.ch.control(fn, **kwargs)


    def button(self, label: str, method: Union[str, Handler], **kwargs: Any) -> str:
        """Demo-only HTML button. Prefer ``bind`` + your ux-dom control."""
        if isinstance(method, str):
            fn = getattr(self, method)
        else:
            fn = method
        from ux_channel.render.kit import demo_button
        return demo_button(self.ch, label, fn, **kwargs)

    def controls(self, *specs: tuple[str, str] | tuple[str, str, dict], **btn_kwargs: Any) -> str:
        """
        Concatenate several buttons::

            badge.controls(("Add", "add", {"trust": {...}}), ("Reset", "reset"))
        """
        parts: list[str] = []
        for spec in specs:
            if len(spec) == 2:
                label, meth = spec  # type: ignore[misc]
                parts.append(self.button(label, meth, **btn_kwargs))
            else:
                label, meth, extra = spec  # type: ignore[misc]
                extra = dict(extra)
                if "args" in extra and "trust" not in extra:
                    extra["trust"] = extra.pop("args")
                parts.append(self.button(label, meth, **{**btn_kwargs, **extra}))
        return "".join(parts)

    def __repr__(self) -> str:
        st = "mounted" if self._mounted else "unmounted"
        return f"<{type(self).__name__} uid={self.uid!r} {st}>"


def use(channel: Any, cls: type[Region], **scope: Any) -> Region:
    """``ch.use(CartBadge)`` → mounted instance."""
    if not isinstance(cls, type) or not issubclass(cls, Region):
        raise TypeError("ch.use expects a Region subclass")
    return cls(channel, **scope).mount()


def attach_region_classes(channel: Any) -> None:
    """Attach ``ch.use`` and ``ch.Region`` for discovery."""
    channel.use = lambda cls, **scope: use(channel, cls, **scope)  # type: ignore[method-assign]
    channel.Region = Region  # type: ignore[attr-defined]
