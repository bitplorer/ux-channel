"""Render package — HTML safety + control attrs (common); heavy modules lazy.

Application-common::

    from ux_channel.render import esc, action_attrs, ControlAttrs, SafeHtml

Power modules (import when needed)::

    from ux_channel.render import morph_ir, placement, renderers
"""
from __future__ import annotations

from typing import Any

from ux_channel.render.html_safe import SafeHtml, esc, mark_safe, user_content
from ux_channel.render.html import ControlAttrs, action_attrs

__all__ = [
    "morph_ir",
    "html_safe",
    "placement",
    "renderers",
    "SafeHtml",
    "esc",
    "mark_safe",
    "user_content",
    "ControlAttrs",
    "action_attrs",
]

_LAZY_MODS = {
    "morph_ir": "ux_channel.render.morph_ir",
    "html_safe": "ux_channel.render.html_safe",
    "placement": "ux_channel.render.placement",
    "renderers": "ux_channel.render.renderers",
}


def __getattr__(name: str) -> Any:
    mod = _LAZY_MODS.get(name)
    if mod is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    val = importlib.import_module(mod)
    globals()[name] = val
    return val
