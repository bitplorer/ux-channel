"""
Bare-bones Channel region primitives — library-agnostic (Tailwind-like utilities).

These are **pure helpers**: no FastAPI, no ux-dom import, no CSS framework lock-in.
Produce HTML strings + Result ops that any host can embed (ux-dom trees, Jinja,
string templates, Starlette responses).

Primitives (like Tailwind utilities)
------------------------------------
- ``uid_sel(uid)``           CSS selector for a region root
- ``region_root(uid, html)`` wrap fragment in ``data-channel-id``
- ``region_attrs(...)``      ``data-channel-*`` attribute string
- ``region_button(...)``     control with signed cap (needs registry)
- ``region_morph(uid, html)``→ Result with morph op
- ``to_html(value)``         coerce str / ``__html__`` / ``__render__`` / ux-dom-like

NOT exported as ``Component`` — that name collides with ux-dom's Component class.
Higher-level widgets live in sibling modules and subclass ``ChannelComponent``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ux_channel.render.html import action_attrs, button as html_button
from ux_channel.render.html_safe import esc
from ux_channel.protocol.ops import morph, toast
from ux_channel.protocol.types import Result


def uid_sel(uid_id: str) -> str:
    """``[data-channel-id=\"…\"]`` or pass-through if already a CSS selector."""
    if uid_id.startswith(("[", "#", ".")):
        return uid_id
    return f'[data-channel-id="{uid_id}"]'


def uid_attr(uid_id: str) -> str:
    return f'data-channel-id="{esc(uid_id)}"'


def region_root(
    uid_id: str,
    inner: str = "",
    *,
    tag: str = "div",
    **attrs: str,
) -> str:
    """
    Bare region shell — the only structural contract Channel needs.

    ::

        region_root("Cart:badge", "<span>3</span>", class_="badge")
    """
    if "class_" in attrs:
        attrs = dict(attrs)
        attrs["class"] = attrs.pop("class_")
    extra = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
    return (
        f"<{tag} {uid_attr(uid_id)}"
        f"{(' ' + extra) if extra else ''}>{inner}</{tag}>"
    )


def region_attrs(
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    cap: Optional[str] = None,
    target: Optional[str] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> str:
    """``data-channel-*`` attributes only — drop onto any tag/library element."""
    sealed = trust
    tgt = uid_sel(target) if target and not target.startswith(("[", "#", ".")) else target
    return action_attrs(action, trust=sealed, cap=cap, target=tgt, extra=extra)


def region_button(
    registry: Any,
    label: str,
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    target: Optional[str] = None,
    mint_cap: bool = True,
    once: bool = False,
    sub: Optional[str] = None,
    class_name: str = "",
    **attrs: Any,
) -> str:
    """Signed control button using any ActionRegistry-like ``.mint``."""
    sealed = dict(trust or {})
    cap = None
    if mint_cap and hasattr(registry, "mint"):
        cap = registry.mint(action, sealed, once=once, sub=sub)
    return html_button(
        label,
        action,
        trust=sealed,
        cap=cap,
        target=uid_sel(target)
        if target and not str(target).startswith(("[", "#", "."))
        else target,
        class_name=class_name,
        **attrs,
    )


def region_morph(
    uid_id: str,
    html: str,
    *extra_ops: Mapping[str, Any],
    notice: Optional[str] = None,
    notice_level: str = "info",
    morph_mode: str = "idiomorph",
) -> Result:
    """One-shot Result: morph region (+ optional toast)."""
    from ux_channel.protocol.ops import toast as toast_op

    ops: list[Any] = [morph(target=uid_sel(uid_id), html=html, morph=morph_mode)]
    ops.extend(extra_ops)
    if notice:
        ops.append(toast_op(notice, level=notice_level))
    return Result.success(*ops)


def to_html(value: Any) -> str:
    """
    Coerce library-native values to HTML **without importing ux-dom**.

    Order:
      1. ``None`` → ``""``
      2. SafeHtml / objects with ``__html__()``
      3. ``str`` / ``bytes``
      4. objects with ``__render__()`` (ux-dom-style)
      5. objects with ``render()`` returning str
      6. ``str(value)`` last resort (escaped)
    """
    if value is None:
        return ""
    from ux_channel.render.html_safe import SafeHtml, esc

    if isinstance(value, SafeHtml):
        return str(value)
    if hasattr(value, "__html__"):
        try:
            return str(value.__html__())
        except Exception:
            pass
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "__render__"):
        try:
            out = value.__render__()
            if isinstance(out, str):
                return out
            return to_html(out)
        except Exception:
            pass
    render = getattr(value, "render", None)
    if callable(render):
        try:
            out = render()
            if isinstance(out, str):
                return out
        except TypeError:
            pass
    return esc(str(value))



@runtime_checkable
class ChannelHost(Protocol):
    """
    Minimal host surface widgets need.

    Implemented by ``Channel`` (dx) and ``RegistryHost`` (bare ActionRegistry).
    """

    @property
    def registry(self) -> Any: ...

    def mint(self, action: str, args: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> str: ...

    def action(self, name: str, **kwargs: Any) -> Any: ...

    def refresh(
        self,
        uid_id: str,
        html: str,
        *extra_ops: Any,
        notice: Optional[str] = None,
        notice_level: str = "info",
    ) -> Result: ...

    def wrap(self, uid_id: str, inner: str, *, tag: str = "div", **attrs: str) -> str: ...

    def redirect(self, href: str) -> Any: ...

    def multi(
        self,
        regions: Mapping[str, str],
        *extra_ops: Any,
        notice: Optional[str] = None,
    ) -> Result: ...

    @property
    def ui(self) -> Any: ...


class RegistryHost:
    """
    Adapter: bare ``ActionRegistry`` → ChannelHost.

    Use when you are not using ``Channel.boot`` (e.g. pure ux-dom + registry)::

        from ux_channel.components import RegistryHost, Counter
        host = RegistryHost(reg)
        counter = Counter(host, uid="Cart:qty").install()
    """

    def __init__(self, registry: Any):
        self.registry = registry

    def mint(self, action: str, args: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> str:
        return self.registry.mint(action, dict(args or {}), **kwargs)

    def action(self, name: str, **kwargs: Any) -> Any:
        return self.registry.action(name, **kwargs)

    def button(self, label: str, action: str, **kwargs: Any) -> str:
        return region_button(self.registry, label, action, **kwargs)

    def refresh(
        self,
        uid_id: str,
        html: str,
        *extra_ops: Any,
        notice: Optional[str] = None,
        notice_level: str = "info",
    ) -> Result:
        return region_morph(
            uid_id, to_html(html), *extra_ops, notice=notice, notice_level=notice_level
        )

    def patch(
        self,
        uid_id: str | Mapping[str, str],
        html: str | None = None,
        *extra_ops: Any,
        notice: Optional[str] = None,
        notice_level: str = "info",
        **kwargs: Any,
    ) -> Result:
        if isinstance(uid_id, Mapping):
            return self.multi(uid_id, *extra_ops, notice=notice)
        if html is None:
            raise TypeError("patch(uid, html) requires html")
        return self.refresh(
            uid_id, html, *extra_ops, notice=notice, notice_level=notice_level, **kwargs
        )

    def wrap(self, uid_id: str, inner: str, *, tag: str = "div", **attrs: str) -> str:
        return region_root(uid_id, to_html(inner), tag=tag, **attrs)

    def form(self, action: str, **kwargs: Any) -> str:
        from ux_channel.render.html import form_open

        sign = kwargs.pop("sign", True)
        sub = kwargs.pop("sub", None)
        cap = self.mint(action, {}, sub=sub) if sign else kwargs.pop("cap", None)
        kwargs.pop("trust", None)
        return form_open(action, cap=cap, **kwargs)

    def attrs(self, action: str, **kwargs: Any) -> str:
        args = dict(kwargs.pop("args", None) or {})
        sign = kwargs.pop("sign", True)
        cap = kwargs.pop("cap", None)
        trust = kwargs.pop("trust", None) or args
        if cap is None and sign:
            cap = self.mint(
                action,
                args,
                **{k: kwargs.pop(k) for k in ("sub", "once", "scopes") if k in kwargs},
            )
        return region_attrs(action, trust=trust, cap=cap, **kwargs)

    @property
    def fail(self) -> "_HostFail":
        return _HostFail(self)

    def redirect(self, href: str) -> Result:
        from ux_channel.protocol.encode import Go

        return Go(href)  # type: ignore[return-value]

    def multi(
        self,
        regions: Mapping[str, str],
        *extra_ops: Any,
        notice: Optional[str] = None,
    ) -> Result:
        ops: list[Any] = [
            morph(target=uid_sel(uid), html=to_html(html)) for uid, html in regions.items()
        ]
        ops.extend(extra_ops)
        if notice:
            from ux_channel.protocol import ops as _ops

            ops.append(_ops.toast(notice))
        return Result.success(*ops)

    @property
    def ui(self) -> Any:
        from ux_channel.host.channel import UiBuilder

        return UiBuilder()


class _HostFail:
    """Minimal fail speech for RegistryHost (no Channel.flow)."""

    def __init__(self, host: RegistryHost):
        self._host = host

    def valid(
        self,
        fields: dict,
        *,
        region: str,
        html: Any,
        message: str = "Please fix the highlighted fields",
        focus: Optional[str] = None,
        notice: bool = False,
    ) -> Result:
        from ux_channel.protocol.ops import focus as focus_op

        ops: list[Any] = [morph(target=uid_sel(region), html=to_html(html))]
        if focus:
            ops.append(focus_op(target=focus, select=True))
        if notice:
            ops.append(toast(message, level="error"))
        return Result.failure("validation", message, *ops, fields=fields)

    def auth(self, message: str = "Please sign in", *, notice: bool = False) -> Result:
        return Result.failure("unauthorized", message)

    def forbidden(self, message: str = "Forbidden", *, notice: bool = False) -> Result:
        return Result.failure("forbidden", message)

    def rate(self, message: str = "Too many requests", *, notice: bool = False) -> Result:
        return Result.failure("rate_limited", message, retryable=True)

    def code(self, code: str, message: str, **kwargs: Any) -> Result:
        return Result.failure(code, message, **kwargs)


def as_host(channel_or_registry: Any) -> ChannelHost:
    """Normalize Channel façade or ActionRegistry to ChannelHost."""
    if isinstance(channel_or_registry, RegistryHost):
        return channel_or_registry  # type: ignore[return-value]
    if hasattr(channel_or_registry, "fail") and hasattr(channel_or_registry, "done"):
        return channel_or_registry  # type: ignore[return-value]
    if hasattr(channel_or_registry, "registry") and hasattr(
        channel_or_registry, "refresh"
    ):
        if hasattr(channel_or_registry, "wrap"):
            return channel_or_registry  # type: ignore[return-value]
    if hasattr(channel_or_registry, "mint") and hasattr(channel_or_registry, "action"):
        return RegistryHost(channel_or_registry)  # type: ignore[return-value]
    raise TypeError(
        "expected Channel, ActionRegistry, or RegistryHost — "
        f"got {type(channel_or_registry)!r}"
    )
