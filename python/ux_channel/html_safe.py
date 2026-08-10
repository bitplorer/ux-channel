"""HTML escaping helpers (SafeHtml, esc, mark_safe) for channel render paths."""

from __future__ import annotations

from typing import Any

_Q = chr(34)
_A = chr(39)


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
