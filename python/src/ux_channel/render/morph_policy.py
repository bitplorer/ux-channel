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
from typing import Any, Mapping

from html5lib import HTMLParser
from html5lib.serializer import HTMLSerializer
from html5lib.treebuilders import getTreeBuilder
from html5lib.treewalkers import getTreeWalker

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
_SVG = "http://www.w3.org/2000/svg"
_MATH = "http://www.w3.org/1998/Math/MathML"
_TAG_NAME = re.compile(r"^[a-z][a-z0-9:-]*$")

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


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _namespace(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag[1:tag.index("}")]
    return "http://www.w3.org/1999/xhtml"


def _drop_element(parent: Any, child: Any) -> None:
    """Remove ``child`` and keep text that followed it."""
    tail = child.tail
    index = list(parent).index(child)
    parent.remove(child)
    if not tail:
        return
    if index == 0:
        parent.text = (parent.text or "") + tail
    else:
        prev = list(parent)[index - 1]
        prev.tail = (prev.tail or "") + tail


def _refused_attr(name: str, value: str | None) -> bool:
    return (
        _event_handler(name)
        or _attr_url_refused(name, value)
        or _js_url_value(name, value)
    )


def _scrub(node: Any) -> None:
    """Drop dangerous elements and attributes in an html5lib tree."""
    for child in list(node):
        tag = getattr(child, "tag", None)
        if not isinstance(tag, str):
            _drop_element(node, child)
            continue
        local = _local_name(tag).lower()
        ns = _namespace(tag)
        if not _TAG_NAME.match(local) or local in _DROP_CONTENT or local in _DROP_TAG:
            _drop_element(node, child)
            continue
        if local == "style" and ns in (_SVG, _MATH):
            _drop_element(node, child)
            continue
        attrs = list(child.attrib.items())
        if local in ("set", "animate") and _anim_sets_handler(
            [(_local_name(key), value) for key, value in attrs]
        ):
            _drop_element(node, child)
            continue
        for key, value in attrs:
            if _refused_attr(_local_name(key), value):
                del child.attrib[key]
        _scrub(child)


def _serialize(fragment: Any) -> str:
    serializer = HTMLSerializer(omit_optional_tags=False, quote_attr_values="always")
    return serializer.render(getTreeWalker("etree")(fragment))


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

    The tree is built with an HTML5 parser (scripting on, so ``noscript`` is
    raw text and svg/math are foreign content). Dangerous elements and
    attributes are removed, then the fragment is serialized. If main's regex
    pass would still change that serialization, the fragment is refused.
    A parse failure drops it.
    """
    if not html:
        return html
    try:
        parser = HTMLParser(tree=getTreeBuilder("etree"))
        fragment = parser.parseFragment(html, container="div", scripting=True)
    except Exception:
        return ""
    _scrub(fragment)
    if _raw_text_disagrees(fragment):
        return ""
    rendered = _serialize(fragment)
    if _regex_strip(rendered) != rendered:
        return ""
    return rendered


def _raw_text_disagrees(node: Any) -> bool:
    """True when raw text still matches main's regex.

    ``<textarea>`` and HTML ``<style>`` keep their contents as text. If that
    text is something the regex would edit, the fragment is refused instead
    of half-stripped.
    """
    for child in node.iter():
        for text in (getattr(child, "text", None), getattr(child, "tail", None)):
            if isinstance(text, str) and text and _regex_strip(text) != text:
                return True
    return False


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
    if policy == "off":
        return ops
    if policy != "strict":
        raise ValueError('morph_html_policy must be "off" or "strict"')
    return [_strict_one(op) for op in ops]
