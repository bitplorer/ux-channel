"""
HTML wiring helpers — attributes and demo tags, not a design system.

First principles
----------------
Product UI is rendered by ux-dom (or templates). This module provides:

- ``action_attrs`` / ``ControlAttrs`` — data-channel-* protocol attributes (ux-channel ownership — not data-dom-*)
- ``form_open`` — progressive-enhance form with cap
- ``button`` — **demo** raw HTML only (prefer ux-dom + control attrs)

``ch.control(...).as_dict()`` / ``.as_ux_dom()`` is the product API.

See: docs/HOW_TO.md, docs/DESIGN.md.
"""
from __future__ import annotations

def _serde():
    from ux_channel.protocol import serde as _m
    return _m



import html
import json
from typing import Any, Mapping, Optional


def json_attr(value: Any) -> str:
    """JSON for embedding in a double-quoted HTML attribute."""
    raw = _serde().dumps(value, default=str)
    return html.escape(raw, quote=True)


def attr_escape(value: str) -> str:
    return html.escape(str(value), quote=True)


class ControlAttrs:
    """
    Ingestible control binding for any UI library.

    * ``str(attrs)`` / ``__html__`` → ``data-channel-action="…" data-channel-cap="…"``
    * ``attrs.as_dict()`` → ``{"data-channel-action": "...", ...}`` for kwargs/spread
    * ``attrs.as_ux_dom()`` → underscore keys some Python HTML DSLs prefer

    ux-dom example::

        button("Add", **ch.control(badge.add, trust_sku=sku).as_dict())
        # or:
        raw(f'<button type="button" {ch.control(badge.add)}>Add</button>')
    """

    __slots__ = ("_parts", "_map")

    def __init__(
        self,
        *,
        action: str,
        trust: Optional[Mapping[str, Any]] = None,
        cap: Optional[str] = None,
        target: Optional[str] = None,
        extra: Optional[Mapping[str, str]] = None,
    ) -> None:
        m: dict[str, str] = {"data-channel-action": str(action)}
        if trust is not None:
            m["data-channel-args"] = _serde().dumps(dict(trust), default=str)
        if cap:
            m["data-channel-cap"] = str(cap)
        if target:
            m["data-channel-target"] = str(target)
        if extra:
            m.update({str(k): str(v) for k, v in extra.items()})
        self._map = m
        self._parts = " ".join(f'{k}="{attr_escape(v)}"' for k, v in m.items())

    def __str__(self) -> str:
        return self._parts

    def __html__(self) -> str:
        return self._parts

    def __render__(self, *a: Any, **k: Any) -> str:
        return self._parts

    def as_dict(self) -> dict[str, str]:
        """Raw attribute map for **kwargs** (ux-dom / builders that HTML-escape).

        Values are **not** HTML-escaped. Do **not** embed with
        ``f'{k}="{v}"'`` — JSON in ``data-channel-args`` will break the
        attribute and the browser client will send empty args (401 cap mismatch).

        For raw HTML strings use ``str(attrs)`` / ``attr_string`` (escaped).
        """
        return dict(self._map)

    @property
    def attr_string(self) -> str:
        """Same as ``str(self)`` — ready for HTML attribute dump."""
        return self._parts

    def as_html(self) -> str:
        """Escaped ``data-channel-*=…`` string for raw HTML templates."""
        return self._parts

    @property
    def cap(self) -> str | None:
        """Signed capability token if minted."""
        return self._map.get("data-channel-cap")

    @property
    def action(self) -> str:
        """Action name bound on this control."""
        return self._map.get("data-channel-action", "")

    def as_ux_dom(self) -> dict[str, str]:
        """
        Underscore form: ``data_channel_action`` (if your tag lib maps _ → -).
        """
        out = {}
        for k, v in self._map.items():
            out[k.replace("-", "_")] = v
        return out

    def __add__(self, other: Any) -> str:
        return self._parts + str(other)

    def __radd__(self, other: Any) -> str:
        return str(other) + self._parts


def action_attrs(
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    cap: Optional[str] = None,
    target: Optional[str] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> str:
    """String form of control attrs (for f-strings). Prefer ``ControlAttrs``."""
    return str(
        ControlAttrs(action=action, trust=trust, cap=cap, target=target, extra=extra)
    )


def button(
    label: str,
    action: str,
    *,
    trust: Optional[Mapping[str, Any]] = None,
    cap: Optional[str] = None,
    target: Optional[str] = None,
    type: str = "button",
    class_name: str = "",
    **attrs: str,
) -> str:
    """
    Demo-only HTML button. Real apps: ux-dom/your button + ``ch.control(...)``.

    Kept for golden-path tests and channel-only demos.
    """
    extra = dict(attrs)
    if class_name:
        extra["class"] = class_name
    extra_s = " ".join(f'{k}="{attr_escape(v)}"' for k, v in extra.items())
    core = action_attrs(action, trust=trust, cap=cap, target=target)
    return (
        f'<button type="{attr_escape(type)}" {core}'
        f'{(" " + extra_s) if extra_s else ""}>{html.escape(label)}</button>'
    )


def form_open(
    action: str,
    *,
    cap: Optional[str] = None,
    target: Optional[str] = None,
    method: str = "post",
    class_name: str = "",
    uid_id: Optional[str] = None,
    **attrs: str,
) -> str:
    """Open form tag with protocol attrs — still not a full form widget."""
    parts = [f'<form method="{attr_escape(method)}"']
    if class_name:
        parts.append(f' class="{attr_escape(class_name)}"')
    parts.append(f" {action_attrs(action, cap=cap, target=target)}")
    if uid_id:
        parts.append(f' data-channel-id="{attr_escape(uid_id)}"')
    for k, v in attrs.items():
        parts.append(f' {k}="{attr_escape(v)}"')
    parts.append(">")
    return "".join(parts)
