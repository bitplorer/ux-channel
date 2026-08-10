"""
Host chrome for bridge islands — class / style / CSS variables.

Boundary
--------
* These attrs go on the **host element** (Placement.attrs) for ux-dom.
* They are **not** automatically npm package options — put library styles in
  ``props`` when the package documents them (e.g. Chart.js ``options``).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Union

__all__ = ["merge_host_style", "normalize_css_vars"]

CssInput = Union[Mapping[str, Any], str, None]


def normalize_css_vars(css: CssInput) -> dict[str, str]:
    """
    Accept::

        {"--accent": "#f00", "color": "white"}   # dict
        "--accent: #f00; color: white"           # raw fragment
        None
    """
    if css is None:
        return {}
    if isinstance(css, str):
        out: dict[str, str] = {}
        for part in css.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
        return out
    if isinstance(css, Mapping):
        out = {}
        for k, v in css.items():
            if v is None:
                continue
            key = str(k).strip()
            # allow accent → --accent for friendliness
            if key and not key.startswith("--") and key.isidentifier():
                # only auto-prefix simple tokens that look like design tokens
                if key in ("accent", "bg", "fg", "track", "border", "radius", "muted"):
                    key = f"--{key}"
            out[key] = str(v).strip()
        return out
    raise TypeError("css must be a dict of properties, a style fragment, or None")


def merge_host_style(
    *,
    style: str = "",
    css: CssInput = None,
) -> str:
    """
    Build a single ``style`` attribute value: css variables + optional style.

    Order: css vars first, then free-form ``style`` (so style can override).
    """
    parts: list[str] = []
    for k, v in normalize_css_vars(css).items():
        if not k:
            continue
        # safety: no braces / quotes injection in property names
        if any(ch in k for ch in (";", "{", "}", "<")):
            continue
        if any(ch in v for ch in ("<", ">")):
            continue
        parts.append(f"{k}: {v}")
    style = (style or "").strip().rstrip(";")
    if style:
        parts.append(style)
    return "; ".join(parts)
