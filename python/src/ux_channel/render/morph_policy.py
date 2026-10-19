"""HTML policy for morph / swap / toast (SECURITY_AUDIT HIGH residual).

Both modes remove ``on*``, ``srcdoc``, and dangerous URLs (``javascript:``,
``vbscript:``, ``data:text/html``, and a control character in a URL
attribute) with html5lib. Off mode keeps ``<script>`` and every other
element. It is not a sanitizer: apps must escape user HTML or set
``morph_html_policy="strict"``.

This replaces main ``83a580a``, where off mode returned the fragment
unchanged. Strict still drops script, iframe, object, and the rest of
the full list.

A fragment is refused when html5lib cannot be imported, the parse fails,
or a second parse of the cleaned output disagrees. Plain text (no ``<``)
and non-HTML ops do not need the parser.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

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
    token = name.strip().lower()
    return (
        _event_handler(name)
        or token == "srcdoc"
        or _attr_url_refused(name, value)
        or _js_url_value(name, value)
    )


def _off_refused_attr(name: str, value: str | None) -> bool:
    """on*, srcdoc, and dangerous URL attributes. Other attributes stay.

    ``data-channel-id="Counter:root"`` is not a URL attribute. The strict
    scrubber's extra ``_js_url_value`` pass would drop it.
    """
    token = name.strip().lower()
    if _event_handler(name) or token == "srcdoc":
        return True
    if _attr_url_refused(name, value):
        return True
    return token == "srcset" and _js_url_value(name, value)


def _scrub_attrs(node: Any) -> None:
    """Remove on*, srcdoc, and dangerous URLs. Keep script and other elements."""
    for child in list(node):
        tag = getattr(child, "tag", None)
        if not isinstance(tag, str):
            continue
        local = _local_name(tag).lower()
        attrs = list(child.attrib.items())
        named = [(_local_name(key), value) for key, value in attrs]
        if local in ("set", "animate") and _anim_sets_handler(named):
            _drop_element(node, child)
            continue
        for key, value in attrs:
            if _off_refused_attr(_local_name(key), value):
                del child.attrib[key]
        _scrub_attrs(child)


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


def _serialize(
    fragment: Any,
    *,
    html_serializer: Callable[..., Any],
    get_tree_walker: Callable[..., Any],
) -> str:
    serializer = html_serializer(omit_optional_tags=False, quote_attr_values="always")
    return serializer.render(get_tree_walker("etree")(fragment))


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


def _import_html5lib() -> tuple[Any, Any, Any, Any]:
    """Load html5lib. Raises when the package is missing.

    html5lib 1.1 was last released on 2020-06-22 and is tracked as a
    dependency to watch. Both modes import it for HTML fragments.
    """
    from html5lib import HTMLParser
    from html5lib.serializer import HTMLSerializer
    from html5lib.treebuilders import getTreeBuilder
    from html5lib.treewalkers import getTreeWalker

    return HTMLParser, HTMLSerializer, getTreeBuilder, getTreeWalker


def _parse_fragment(html: str, html_parser: Any, get_tree_builder: Any) -> Any:
    parser = html_parser(tree=get_tree_builder("etree"))
    return parser.parseFragment(html, container="div", scripting=True)


def _render(fragment: Any, html_serializer: Any, get_tree_walker: Any) -> str:
    return _serialize(
        fragment,
        html_serializer=html_serializer,
        get_tree_walker=get_tree_walker,
    )


def _checked_fragment(html: str, *, drop_elements: bool) -> str:
    """Return cleaned HTML, or ``""`` when the check cannot finish.

    ``drop_elements`` is the strict list. Off mode only removes attributes.
    Plain text never reaches the parser.
    """
    if not html:
        return html
    if not drop_elements and "<" not in html:
        return html
    try:
        html_parser, html_serializer, get_tree_builder, get_tree_walker = (
            _import_html5lib()
        )
    except Exception:
        return ""
    try:
        fragment = _parse_fragment(html, html_parser, get_tree_builder)
    except Exception:
        return ""
    if drop_elements:
        _scrub(fragment)
        if _raw_text_disagrees(fragment):
            return ""
    else:
        _scrub_attrs(fragment)
    rendered = _render(fragment, html_serializer, get_tree_walker)
    if drop_elements and _regex_strip(rendered) != rendered:
        return ""
    try:
        again = _parse_fragment(rendered, html_parser, get_tree_builder)
        again_rendered = _render(again, html_serializer, get_tree_walker)
    except Exception:
        return ""
    if again_rendered != rendered:
        return ""
    return rendered


def strip_off_html(html: str) -> str:
    """Remove on*, srcdoc, and dangerous URLs. Keep script and other markup.

    Refused when html5lib is missing, the parse fails, or a second parse of
    the cleaned output disagrees. Plain text is returned unchanged.
    """
    return _checked_fragment(html, drop_elements=False)


def strip_dangerous_html(html: str) -> str:
    """Remove script-shaped markup. Leaves ux-dom data-* and custom tags.

    The tree is built with an HTML5 parser (scripting on, so ``noscript`` is
    raw text and svg/math are foreign content). Dangerous elements and
    attributes are removed, then the fragment is serialized. If main's regex
    pass would still change that serialization, or a second parse disagrees,
    the fragment is refused. A parse failure drops it.
    """
    return _checked_fragment(html, drop_elements=True)


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


def _filter_one(op: Any, scrub: Callable[[str], str]) -> Any:
    """Run ``scrub`` on one op and any ops nested inside it."""
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
        cloned["html"] = scrub(str(cloned.get("html") or ""))
    elif name == "toast":
        for key in ("message", "text", "display"):
            if key in cloned and cloned[key] is not None:
                cloned[key] = scrub(str(cloned[key]))
    nested = cloned.get("ops")
    if isinstance(nested, list):
        cloned["ops"] = [_filter_one(child, scrub) for child in nested]
    return cloned


def apply_morph_policy(ops: list[Any], *, policy: str = "off") -> list[Any]:
    """Remove refused vectors from morph, swap, and toast in both modes.

    Off removes ``on*``, ``srcdoc``, and dangerous URLs and keeps
    ``<script>`` and other markup. Strict applies the full drop list.
    Both walk ``seq``, ``timer.set``, ``invoke``, and any other op that
    carries an ``ops`` list. Plain text and non-HTML ops are unchanged.
    """
    if policy not in ("off", "strict"):
        raise ValueError('morph_html_policy must be "off" or "strict"')
    scrub = strip_dangerous_html if policy == "strict" else strip_off_html
    return [_filter_one(op, scrub) for op in ops]
