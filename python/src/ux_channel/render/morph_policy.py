"""Opt-in strict HTML policy for morph / swap / toast (SECURITY_AUDIT HIGH residual).

Default is off — ux-dom fragments and app-owned markup stay intact.
``ChannelConfig.morph_html_policy = "strict"`` strips script/iframe/object
and inline event handlers from morph and swap HTML and from toast text.

Must not break ux-dom: data-* attributes, custom elements, and region
slots are preserved. This is not a full sanitizer; it is a fail-closed
strip of the residual XSS shapes named in SECURITY_AUDIT.md.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Mapping

__all__ = ["apply_morph_policy", "strip_dangerous_html"]

# Elements whose contents are script or navigation context.
_DROP_CONTENT = frozenset({"script", "iframe", "object"})
# Void elements that should not swallow the rest of the fragment.
_DROP_TAG = frozenset({"embed", "link", "meta", "base"})
_WS = " \t\n\r\f"


def _event_handler(name: str) -> bool:
    token = name.strip().lower()
    return len(token) > 2 and token.startswith("on")


def _attr_url_refused(name: str, value: str | None) -> bool:
    """Script-scheme URL attributes. Entities are decoded before the check.

    Imported inside the call so this module can load without a cycle:
    security imports apply_morph_policy at module level.
    """
    if value is None:
        return False
    from ux_channel.security.security import _is_url_attr, _unsafe_url_attr

    if not _is_url_attr(name):
        return False
    return _unsafe_url_attr(name, value)


def _excise_attrs(raw: str, drop: set[str]) -> str:
    """Remove attributes whose names are in ``drop`` from one start tag."""
    if not raw.startswith("<") or ">" not in raw:
        return raw
    i = 1
    while i < len(raw) and raw[i] not in _WS + "/>":
        i += 1
    parts = [raw[:i]]
    while i < len(raw):
        ws_at = i
        while i < len(raw) and raw[i] in _WS:
            i += 1
        ws = raw[ws_at:i]
        if i >= len(raw):
            parts.append(ws)
            break
        if raw[i] == ">":
            parts.append(">")
            break
        if raw[i] == "/" and i + 1 < len(raw) and raw[i + 1] == ">":
            parts.append("/>")
            break
        if raw[i] == "/":
            # <svg/onload=...> — solidus before the attribute name.
            i += 1
            continue
        name_at = i
        while i < len(raw) and raw[i] not in _WS + "=/>":
            i += 1
        name = raw[name_at:i]
        if i < len(raw) and raw[i] in _WS:
            j = i
            while j < len(raw) and raw[j] in _WS:
                j += 1
            if j < len(raw) and raw[j] == "=":
                i = j
        if i < len(raw) and raw[i] == "=":
            i += 1
            while i < len(raw) and raw[i] in _WS:
                i += 1
            if i < len(raw) and raw[i] in "\"'":
                quote = raw[i]
                i += 1
                while i < len(raw) and raw[i] != quote:
                    i += 1
                if i < len(raw):
                    i += 1
            else:
                while i < len(raw) and raw[i] not in _WS + ">":
                    i += 1
        if name.lower() in drop:
            continue
        parts.append(ws)
        parts.append(raw[name_at:i])
    return "".join(parts)


class _StrictHTMLParser(HTMLParser):
    """Rebuild a fragment with dangerous elements and attributes removed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._out: list[str] = []
        self._drop = 0

    def _dropped_names(self, attrs: list[tuple[str, str | None]]) -> set[str]:
        drop: set[str] = set()
        for name, value in attrs:
            if _event_handler(name) or _attr_url_refused(name, value):
                drop.add(name.lower())
        return drop

    def _emit_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        if self._drop:
            if tag in _DROP_CONTENT:
                self._drop += 1
            return
        if tag in _DROP_CONTENT:
            self._drop = 1
            return
        if tag in _DROP_TAG:
            return
        drop = self._dropped_names(attrs)
        if drop:
            self._out.append(_excise_attrs(raw, drop))
        else:
            self._out.append(raw)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._emit_start(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._drop:
            return
        if tag in _DROP_CONTENT or tag in _DROP_TAG:
            return
        self._emit_start(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._drop:
            if tag in _DROP_CONTENT:
                self._drop -= 1
            return
        if tag in _DROP_CONTENT or tag in _DROP_TAG:
            return
        self._out.append("</" + tag + ">")

    def handle_data(self, data: str) -> None:
        if not self._drop:
            self._out.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._drop:
            self._out.append("&" + name + ";")

    def handle_charref(self, name: str) -> None:
        if not self._drop:
            self._out.append("&#" + name + ";")

    def handle_comment(self, data: str) -> None:
        if not self._drop:
            self._out.append("<!--" + data + "-->")

    def result(self) -> str:
        return "".join(self._out)


def strip_dangerous_html(html: str) -> str:
    """Remove script-shaped markup. Leaves ux-dom data-* and custom tags.

    Uses the stdlib HTML parser so ``<svg/onload=...>``, unquoted
    ``href=javascript:``, and entity-encoded schemes (``java&#115;cript:``)
    are seen after the browser's attribute parse. A parse failure drops the
    fragment.
    """
    if not html:
        return html
    parser = _StrictHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    return parser.result()


def _strict_one(op: Any) -> Any:
    """Strip one op and any ops nested inside it."""
    body = op
    if not isinstance(op, Mapping):
        to_dict = getattr(op, "to_dict", None)
        if callable(to_dict):
            try:
                body = to_dict()
            except Exception:
                return op
    if not isinstance(body, Mapping):
        return op
    cloned = dict(body)
    name = str(cloned.get("op") or "")
    if name in ("morph", "swap") and "html" in cloned:
        cloned["html"] = strip_dangerous_html(str(cloned.get("html") or ""))
    elif name == "toast":
        for key in ("message", "text", "display"):
            if key in cloned and cloned[key] is not None:
                cloned[key] = strip_dangerous_html(str(cloned[key]))
    nested = cloned.get("ops")
    if isinstance(nested, list):
        cloned["ops"] = [_strict_one(child) for child in nested]
    return cloned


def apply_morph_policy(ops: list[Any], *, policy: str = "off") -> list[Any]:
    """Filter morph/swap/toast ops when policy=strict. ``off`` returns ops unchanged.

    Strict mode walks ``seq``, ``timer.set``, ``invoke``, and any other op
    that carries an ``ops`` list.
    """
    if (policy or "off").lower() != "strict":
        return ops
    return [_strict_one(op) for op in ops]
