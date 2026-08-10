"""Render package — HTML safety, morph IR, placement, HTML renderers.

Preferred::

    from ux_channel.render import morph_ir, html_safe, placement, renderers
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.render import html_safe, morph_ir, placement, renderers
from ux_channel.render.html_safe import SafeHtml, esc, mark_safe, user_content
from ux_channel.render.html import ControlAttrs, action_attrs

PACKAGE = "render"
__all__ = [
    "PACKAGE",
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
