"""Opt-in strict HTML policy for morph / toast (SECURITY_AUDIT HIGH residual).

Default is off — ux-dom fragments and app-owned markup stay intact.
``ChannelConfig.morph_html_policy = "strict"`` strips script/iframe/object
and inline event handlers from morph HTML and toast display text.

Must not break ux-dom: data-* attributes, custom elements, and region
slots are preserved. This is not a full sanitizer; it is a fail-closed
strip of the residual XSS shapes named in SECURITY_AUDIT.md.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

__all__ = ["apply_morph_policy", "strip_dangerous_html"]

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


def strip_dangerous_html(html: str) -> str:
    """Remove script-shaped markup. Leaves ux-dom data-* and custom tags."""
    if not html:
        return html
    out = _SCRIPTISH.sub("", html)
    out = _SCRIPTISH_EMPTY.sub("", out)
    out = _ON_ATTR.sub("", out)
    out = _ON_ATTR_UNQUOTED.sub("", out)
    out = _JS_HREF.sub("", out)
    return out


def apply_morph_policy(ops: list[Any], *, policy: str = "off") -> list[Any]:
    """Filter morph/toast ops in place when policy=strict."""
    if (policy or "off").lower() != "strict":
        return ops
    out: list[Any] = []
    for op in ops:
        body = op
        if hasattr(op, "to_dict"):
            try:
                body = op.to_dict()
            except Exception:
                body = op
        if isinstance(body, Mapping):
            name = str(body.get("op") or "")
            if name == "morph" and "html" in body:
                cloned = dict(body)
                cloned["html"] = strip_dangerous_html(str(cloned.get("html") or ""))
                out.append(cloned)
                continue
            if name == "toast":
                cloned = dict(body)
                for key in ("message", "text", "display"):
                    if key in cloned and cloned[key] is not None:
                        cloned[key] = strip_dangerous_html(str(cloned[key]))
                out.append(cloned)
                continue
        out.append(op)
    return out
