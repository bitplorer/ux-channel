"""
Demo / SSR HTML adapters — **the only module that emits markup strings**.

Core returns Placement / ControlAttrs / Result.
Use this for create-app, tests, and plain-string hosts.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Optional, Sequence, Union

from ux_channel.render.html import button as html_button, form_open
from ux_channel.render.placement import Placement, ScriptRef

__all__ = [
    "script_tags",
    "attr_string",
    "placement_head",
    "placement_body_open",
    "demo_button",
    "demo_page",
    "demo_link",
    "demo_form",
    "demo_submit",
    "mount_html",
    "demo_scripts",
    "fx_script_tags",
    "ui_script_tags",
    "bridge_script_tags",
]


def script_tags(scripts: Any) -> str:
    """
    Render ``<script src=…>`` tags.

    Accepts Placement, MediaPlugin / RtcPlugin bags, ScriptRef sequences,
    or a bag that already has ``scripts_html``.
    """
    if isinstance(scripts, str):
        return scripts
    if isinstance(scripts, Placement):
        refs = scripts.scripts
    elif hasattr(scripts, "to_placement") and callable(scripts.to_placement):
        return script_tags(scripts.to_placement())
    elif hasattr(scripts, "scripts_html") and getattr(scripts, "scripts_html"):
        return str(scripts.scripts_html)
    elif hasattr(scripts, "scripts") and not isinstance(scripts, (str, bytes)):
        refs = scripts.scripts  # type: ignore[assignment]
    else:
        refs = tuple(scripts)  # type: ignore[arg-type]
    parts: list[str] = []
    for s in refs:
        if isinstance(s, Mapping):
            src = escape(str(s.get("src", "")), quote=True)
            module = bool(s.get("module"))
            defer = bool(s.get("defer", True))
            sid = s.get("id")
        else:
            src = escape(s.src, quote=True)
            module = bool(s.module)
            defer = bool(s.defer)
            sid = s.id
        typ = ' type="module"' if module else ""
        defer_a = " defer" if defer and not module else ""
        id_a = f' id="{escape(str(sid), quote=True)}"' if sid else ""
        parts.append(f'<script src="{src}"{typ}{defer_a}{id_a}></script>')
    return "\n".join(parts)


def attr_string(attrs: Any) -> str:
    """Render HTML attribute string from attr dict, Placement, or plugin bag."""
    if isinstance(attrs, str):
        return attrs
    if isinstance(attrs, Placement):
        m = attrs.attrs
    elif hasattr(attrs, "attrs") and isinstance(getattr(attrs, "attrs"), Mapping):
        m = attrs.attrs
    elif hasattr(attrs, "attr_string") and isinstance(getattr(attrs, "attr_string"), str):
        return str(attrs.attr_string)
    else:
        m = attrs
    parts = []
    for k, v in m.items():
        if v == "":
            parts.append(str(k))
        else:
            parts.append(f'{k}="{escape(str(v), quote=True)}"')
    return " ".join(parts)


def placement_head(p: Placement, *, extra: str = "") -> str:
    bits = [script_tags(p)]
    if p.client:
        bits.append(
            f'<script type="application/json" id="ux-placement-client">'
            f"{p.client_json}</script>"
        )
    if extra:
        bits.append(extra)
    return "\n".join(bits)


def placement_body_open(p: Placement, tag: str = "body") -> str:
    a = attr_string(p)
    return f"<{tag} {a}>" if a else f"<{tag}>"


def demo_scripts(ch: Any, **kwargs: Any) -> str:
    """Script tags from ``ch.runtime(**kwargs)``."""
    return script_tags(ch.runtime(**kwargs))


def mount_html(
    host: Mapping[str, Any] | Placement,
    *,
    tag: str = "div",
    inner: str = "",
    class_name: str = "",
) -> str:
    if isinstance(host, Placement):
        attrs = dict(host.attrs)
        if class_name:
            attrs["class"] = class_name
        return f"<{tag} {attr_string(attrs)}>{inner}</{tag}>"
    attrs = dict(host.get("attrs") or host)
    if class_name:
        attrs["class"] = class_name
    t = host.get("tag", tag)
    inn = host.get("inner", inner)
    return f"<{t} {attr_string(attrs)}>{inn}</{t}>"


def demo_button(
    ch: Any,
    label: str,
    action: Any,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    target: Optional[str] = None,
    mint_cap: bool = True,
    sub: Optional[str] = None,
    once: bool = False,
    class_name: str = "",
    **trust_or_attrs: Any,
) -> str:
    from ux_channel.host.channel import sel

    sealed: dict[str, Any] = dict(trust or {})
    html_attrs: dict[str, str] = {}
    for k, v in trust_or_attrs.items():
        if k.startswith("trust_") and len(k) > 6:
            sealed[k[6:]] = v
        else:
            html_attrs[str(k)] = str(v)
    action_name, target = ch._resolve_action_target(action, target)
    cap = None
    if mint_cap:
        cap = ch.registry.mint(action_name, sealed, sub=sub, once=once)
    tgt = (
        sel(target)
        if target and not str(target).startswith(("[", "#", "."))
        else target
    )
    return html_button(
        label,
        action_name,
        trust=sealed,
        cap=cap,
        target=tgt,
        class_name=class_name,
        **html_attrs,
    )


def demo_link(
    ch: Any,
    label: str,
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    target: Optional[str] = None,
    mint_cap: bool = True,
    sub: Optional[str] = None,
    once: bool = False,
    class_name: str = "",
    href: str = "#",
    **trust_or_attrs: Any,
) -> str:
    from ux_channel.host.channel import sel
    from ux_channel.render.html import action_attrs

    sealed: dict[str, Any] = dict(trust or {})
    html_attrs: dict[str, str] = {}
    for k, v in trust_or_attrs.items():
        if k.startswith("trust_") and len(k) > 6:
            sealed[k[6:]] = v
        else:
            html_attrs[str(k)] = str(v)
    args = trust_or_attrs.get("args")
    if isinstance(args, Mapping):
        sealed.update(args)
        html_attrs.pop("args", None)
    elif "args" in html_attrs:
        html_attrs.pop("args", None)
    action_name, target = ch._resolve_action_target(action, target)
    cap = None
    if mint_cap:
        cap = ch.registry.mint(action_name, sealed, sub=sub, once=once)
    tgt = (
        sel(target)
        if target and not str(target).startswith(("[", "#", "."))
        else target
    )
    attrs = action_attrs(
        action_name,
        trust=sealed,
        cap=cap,
        target=tgt,
    )
    extra = " ".join(f'{k}="{escape(v, quote=True)}"' for k, v in html_attrs.items())
    cls = f' class="{escape(class_name, quote=True)}"' if class_name else ""
    return (
        f'<a href="{escape(href, quote=True)}"{cls} {attrs}'
        f'{(" " + extra) if extra else ""}>{escape(label)}</a>'
    )


def demo_form(
    ch: Any,
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    target: Optional[str] = None,
    mint_cap: bool = True,
    sub: Optional[str] = None,
    once: bool = False,
    method: str = "post",
    class_name: str = "",
    uid_id: Optional[str] = None,
    **extra: Any,
) -> str:
    sealed = dict(trust or {})
    action_name, target = ch._resolve_action_target(action, target)
    cap = None
    if mint_cap:
        cap = ch.registry.mint(action_name, sealed, sub=sub, once=once)
    extra.pop("trust", None)
    return form_open(
        action_name,
        cap=cap,
        target=target,
        method=method,
        class_name=class_name,
        uid_id=uid_id,
        **{str(k): str(v) for k, v in extra.items()},
    )


def demo_submit(label: str = "Save", *, class_name: str = "", **attrs: Any) -> str:
    cls = f' class="{escape(class_name, quote=True)}"' if class_name else ""
    extra = " ".join(
        f'{escape(str(k), quote=True)}="{escape(str(v), quote=True)}"'
        for k, v in attrs.items()
    )
    return (
        f'<button type="submit"{cls}'
        f'{(" " + extra) if extra else ""}>{escape(label)}</button>'
    )


def _part_html(part: Any) -> str:
    if part is None:
        return ""
    if isinstance(part, str):
        return part
    if hasattr(part, "html") and callable(part.html):
        try:
            return str(part.html())
        except TypeError:
            pass
    if hasattr(part, "render") and callable(part.render):
        try:
            return str(part.render())
        except TypeError:
            pass
    if hasattr(part, "__html__"):
        return str(part.__html__())
    return str(part)


def demo_page(
    ch: Any,
    *parts: Any,
    title: str = "ux-channel",
    bridge: bool = True,
    inspector: bool | None = None,
    dev: bool | None = None,
    webrtc: bool | None = None,
    body_kwargs: Optional[Mapping[str, Any]] = None,
    head_extra: str = "",
) -> str:
    """
    Minimal full HTML document for demos and scaffold templates.

    ``*parts`` may be strings, region objects (``.html()``), or components.
    """
    body = "\n".join(_part_html(p) for p in parts if p is not None)
    scripts = demo_scripts(ch, bridge=bridge, inspector=inspector, dev=dev, webrtc=webrtc)
    attrs = ch.body_attrs(
        dev=dev,
        inspector=inspector,
        webrtc=webrtc if webrtc else False,
        **dict(body_kwargs or {}),
    )
    body_open = f"<body {attr_string(attrs)}>" if attrs else "<body>"
    return (
        f"<!doctype html>\n<html lang=\"en\"><head>\n"
        f'<meta charset="utf-8"/>\n'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"/>\n'
        f"<title>{escape(title)}</title>\n"
        f"{scripts}\n{head_extra}\n</head>\n"
        f"{body_open}\n{body}\n</body></html>"
    )


def fx_script_tags(*, bridge: bool = True) -> str:
    """
    Demo scripts for stunning ux-fx bridges.

    After Channel runtime scripts, include::

        from ux_channel.render.kit import fx_script_tags
        # … + fx_script_tags()
    """
    tags = []
    if bridge:
        tags.append('<script src="/ux-channel/static/ux-bridge.js" defer></script>')
    tags.append('<script src="/ux-channel/static/adapters/ux-fx.js" defer></script>')
    return "\n".join(tags)


def ui_script_tags(*, bridge: bool = True) -> str:
    """Scripts for high-value UI bridges (leaflet, select, quill, …)."""
    tags = []
    if bridge:
        tags.append('<script src="/ux-channel/static/ux-bridge.js" defer></script>')
    tags.append('<script src="/ux-channel/static/adapters/ux-ui.js" defer></script>')
    return "\n".join(tags)


def bridge_script_tags(*, fx: bool = True, ui: bool = True) -> str:
    """ux-bridge + optional ux-fx + ux-ui adapter packs."""
    tags = ['<script src="/ux-channel/static/ux-bridge.js" defer></script>']
    if fx:
        tags.append('<script src="/ux-channel/static/adapters/ux-fx.js" defer></script>')
    if ui:
        tags.append('<script src="/ux-channel/static/adapters/ux-ui.js" defer></script>')
    return "\n".join(tags)
