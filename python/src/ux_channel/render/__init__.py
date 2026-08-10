"""Render package — HTML safety, morph IR, placement, HTML renderers.

Preferred::

    from ux_channel.render import morph_ir, html_safe, placement, renderers
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.render import html_safe, morph_ir, placement, renderers

PACKAGE = "render"
__all__ = ["PACKAGE", "morph_ir", "html_safe", "placement", "renderers"]
