"""Paint package — morph IR, HTML safety, placement.

Preferred::

    from ux_channel.paint import morph_ir, html_safe, placement
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.paint import morph_ir
from ux_channel.paint import html_safe
from ux_channel.paint import placement

PACKAGE = "paint"
__all__ = ["PACKAGE", "morph_ir", "html_safe", "placement"]
