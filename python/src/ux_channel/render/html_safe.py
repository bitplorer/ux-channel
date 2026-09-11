"""HTML escaping helpers (SafeHtml, esc, mark_safe) for channel render paths.

Soft 1: HTML lowering prefers ux-dom (pin e8be99a) when importable.
Stdlib ``html.escape`` if ux-dom is absent. Channel does not own HTML.
Private helpers below are not public API — do not add them to ``__all__``.
"""

from __future__ import annotations

import html as html_lib
from typing import Any

_Q = chr(34)
_A = chr(39)
_UNSET = object()
_UX_ESCAPE: Any = _UNSET
_UX_SERIALIZE: Any = _UNSET


class SafeHtml(str):
    def __html__(self) -> str:
        return str(self)


def esc(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, SafeHtml):
        return str(value)
    s = str(value)
    s = s.replace("&", "&" + "amp;")
    s = s.replace("<", "&" + "lt;")
    s = s.replace(">", "&" + "gt;")
    s = s.replace(_Q, "&" + "quot;")
    s = s.replace(_A, "&#x27;")
    return s


def safe_text(value: Any) -> str:
    return esc(value)


def attr(name: str, value: Any) -> str:
    return name + "=" + _Q + esc(value) + _Q


def user_content(value: Any, *, tag: str = "span", class_name: str = "") -> str:
    cls = (" class=" + _Q + esc(class_name) + _Q) if class_name else ""
    return "<" + tag + cls + ">" + esc(value) + "</" + tag + ">"


def mark_safe(html: str) -> SafeHtml:
    return SafeHtml(html)


def _html_escape(data: Any, *, quote: bool = True) -> str:
    """Prefer ux-dom ``escape``; stdlib ``html.escape`` if ux-dom is absent."""
    global _UX_ESCAPE
    if _UX_ESCAPE is _UNSET:
        try:
            from ux_dom.dom.src.utils import escape as ux_escape

            _UX_ESCAPE = ux_escape
        except Exception:
            _UX_ESCAPE = None
    if _UX_ESCAPE is not None:
        if data is None:
            data = ""
        return _UX_ESCAPE(data, quote=quote)
    if data is None:
        return ""
    return html_lib.escape(str(data), quote=quote)


def _ux_dom_to_html(value: Any) -> str | None:
    """Owner serialize when ux-dom can render ``value``. None if absent/n/a."""
    global _UX_SERIALIZE
    if _UX_SERIALIZE is _UNSET:
        try:
            from ux_dom.response.serialize import is_html_renderable, to_html_bytes

            _UX_SERIALIZE = (is_html_renderable, to_html_bytes)
        except Exception:
            _UX_SERIALIZE = None
    if _UX_SERIALIZE is None:
        return None
    is_html_renderable, to_html_bytes = _UX_SERIALIZE
    if not is_html_renderable(value):
        return None
    return to_html_bytes(value).decode("utf-8")
