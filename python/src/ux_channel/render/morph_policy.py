"""Opt-in strict HTML policy for morph / swap / toast (SECURITY_AUDIT HIGH residual).

Default is off — ux-dom fragments and app-owned markup stay intact.
``ChannelConfig.morph_html_policy = "strict"`` strips script/iframe/object
and inline event handlers from morph and swap HTML and from toast text.

Must not break ux-dom: data-* attributes, custom elements, and region
slots are preserved. This is not a full sanitizer; it is a fail-closed
strip of the residual XSS shapes named in SECURITY_AUDIT.md.

A fragment is kept only when both passes accept it: the HTML parser pass,
then the regex pass from main (83a580a). The parser pass drops raw-text
elements the browser does not treat the way ``html.parser`` does.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping

__all__ = ["apply_morph_policy", "strip_dangerous_html"]

# Elements whose contents are script, raw text, or navigation context.
# ``style`` is not in this set: a browser treats it as raw text only in the
# HTML namespace. Inside svg/math it is dropped separately.
_DROP_CONTENT = frozenset(
    {
        "script",
        "iframe",
        "object",
        "noscript",
        "xmp",
        "noembed",
        "noframes",
        "plaintext",
        "template",
    }
)
# Void elements that should not swallow the rest of the fragment.
_DROP_TAG = frozenset({"embed", "link", "meta", "base"})
_FOREIGN = frozenset({"svg", "math"})
_WS = " \t\n\r\f"

# Main's regex stripper (83a580a). Second pass: anything it removes stays
# removed, including shapes the parser rewrote into a match.
_SCRIPTISH = re.compile(
    r"<(script|iframe|object|embed|link|meta|base)\b[^>]*>.*?</\1\s*>",
    re.I | re.S,
)
_SCRIPTISH_EMPTY = re.compile(
    r"<(script|iframe|object|embed|link|meta|base)\b[^>]*/\s*>",
    re.I,
)
_ON_ATTR = re.compile(r"""\s+on[a-z]+\s*=\s*(['"]).*?\1""", re.I | re.S)
_ON_ATTR_UNQUOTED = re.compile(r"""\s+on[a-z]+\s*=\s*[^\s>]+""", re.I)
_JS_HREF = re.compile(
    r"""\s(href|src|xlink:href)\s*=\s*(['"])\s*javascript:[^'"]*\2""",
    re.I,
)


def _event_handler(name: str) -> bool:
    token = name.strip().lower()
    return len(token) > 2 and token.startswith("on")


def _anim_sets_handler(attrs: list[tuple[str, str | None]]) -> bool:
    """``<set attributeName=onmouseover>`` installs a handler."""
    for name, value in attrs:
        if name.strip().lower() != "attributename" or not value:
            continue
        if _event_handler(value):
            return True
    return False


def _js_url_value(name: str, value: str | None) -> bool:
    """True when the value is a script URL, including one srcset candidate.

    ``values=javascript:`` on an SVG animation is not an href attribute, and
    a srcset list is more than one URL. Both still have to go.
    """
    if not value:
        return False
    from ux_channel.security.security import _unsafe_url_attr

    if _unsafe_url_attr("href", value):
        return True
    if name.strip().lower() != "srcset":
        return False
    for part in value.split(","):
        bits = part.strip().split()
        if bits and _unsafe_url_attr("href", bits[0]):
            return True
    return False


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
    """Rebuild a fragment with dangerous elements and attributes removed.

    ``style`` is raw text for ``html.parser`` in every namespace. A browser
    does that only in the HTML namespace, so an ``<img>`` inside
    ``<svg><style>`` is a real element. ``noscript`` (scripting on) ends at
    the first ``</noscript>``, including one hidden in an attribute.
    """

    # ``style`` is omitted on purpose. ``noscript`` is raw text because
    # scripting=True, which is how a browser with scripts enabled parses it.
    # typeshed marks this Final; overriding it is the documented extension.
    CDATA_CONTENT_ELEMENTS = ("script", "xmp", "iframe", "noembed", "noframes")  # type: ignore[misc]

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False, scripting=True)
        self._out: list[str] = []
        self._open: list[str] = []
        self._drop_stack: list[str] = []

    def _in_foreign(self) -> bool:
        return any(tag in _FOREIGN for tag in self._open)

    def _opens_drop(self, tag: str) -> bool:
        if tag in _DROP_CONTENT:
            return True
        return tag == "style" and self._in_foreign()

    def _pop_open(self, tag: str) -> None:
        if tag not in self._open:
            return
        while self._open:
            found = self._open.pop()
            if found == tag:
                return

    def _dropped_names(self, attrs: list[tuple[str, str | None]]) -> set[str]:
        drop: set[str] = set()
        for name, value in attrs:
            if (
                _event_handler(name)
                or _attr_url_refused(name, value)
                or _js_url_value(name, value)
            ):
                drop.add(name.lower())
        return drop

    def _emit_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        drop = self._dropped_names(attrs)
        if drop:
            self._out.append(_excise_attrs(raw, drop))
        else:
            self._out.append(raw)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        # Push first so a child can see svg/math already open.
        self._open.append(tag)
        if self._drop_stack:
            if self._opens_drop(tag):
                self._drop_stack.append(tag)
            return
        if self._opens_drop(tag) or (
            tag in ("set", "animate") and _anim_sets_handler(attrs)
        ):
            self._drop_stack.append(tag)
            return
        if tag in _DROP_TAG:
            return
        self._emit_start(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._drop_stack:
            return
        if tag in _DROP_CONTENT or tag in _DROP_TAG:
            return
        if tag == "style" and self._in_foreign():
            return
        if tag in ("set", "animate") and _anim_sets_handler(attrs):
            return
        self._emit_start(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        self._pop_open(tag)
        if self._drop_stack:
            if self._drop_stack[-1] == tag:
                self._drop_stack.pop()
            return
        self._out.append("</" + tag + ">")

    def handle_data(self, data: str) -> None:
        if not self._drop_stack:
            self._out.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._drop_stack:
            self._out.append("&" + name + ";")

    def handle_charref(self, name: str) -> None:
        if not self._drop_stack:
            self._out.append("&#" + name + ";")

    def handle_comment(self, data: str) -> None:
        if not self._drop_stack:
            self._out.append("<!--" + data + "-->")

    def result(self) -> str:
        return "".join(self._out)


def _regex_strip(html: str) -> str:
    """Main's regex pass. Run it on the parser's output, not instead of it."""
    if not html:
        return html
    out = _SCRIPTISH.sub("", html)
    out = _SCRIPTISH_EMPTY.sub("", out)
    out = _ON_ATTR.sub("", out)
    out = _ON_ATTR_UNQUOTED.sub("", out)
    out = _JS_HREF.sub("", out)
    return out


def strip_dangerous_html(html: str) -> str:
    """Remove script-shaped markup. Leaves ux-dom data-* and custom tags.

    The parser pass sees ``<svg/onload=...>``, unquoted ``href=javascript:``,
    and entity-encoded schemes. It drops ``noscript`` (scripting on) and
    ``style`` inside svg or math, plus the other raw-text elements. The regex
    pass then removes anything main's stripper would still match. A fragment
    is kept only when both passes accept it. A parse failure drops it.
    """
    if not html:
        return html
    parser = _StrictHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    return _regex_strip(parser.result())


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
