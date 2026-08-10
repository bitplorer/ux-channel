"""Zone: **render**

HTML safety, morph IR, placement — **how paint reaches the client**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``html`` — Control attrs / demo HTML helpers
* ``html_safe`` — SafeHtml / esc
* ``html_document`` — Document Placement (no HTML strings)
* ``morph_ir`` — Multi-surface morph IR
* ``projections`` — Project morph IR to surfaces
* ``placement`` — Framework-agnostic attrs/scripts
* ``render`` — HtmlRenderer protocol
* ``slot_compile`` — Stable uid compile from trees
* ``response`` — FastAPI/Starlette HTML responses
* ``demo`` — Demo SSR markup only
* ``static`` — SUBPACKAGE: client JS (ux-channel.js)
"""
from __future__ import annotations

ZONE = "render"
DESCRIPTION = 'HTML safety, morph IR, placement — **how paint reaches the client**.'

MEMBERS: dict[str, str] = {
    'html': 'Control attrs / demo HTML helpers',
    'html_safe': 'SafeHtml / esc',
    'html_document': 'Document Placement (no HTML strings)',
    'morph_ir': 'Multi-surface morph IR',
    'projections': 'Project morph IR to surfaces',
    'placement': 'Framework-agnostic attrs/scripts',
    'render': 'HtmlRenderer protocol',
    'slot_compile': 'Stable uid compile from trees',
    'response': 'FastAPI/Starlette HTML responses',
    'demo': 'Demo SSR markup only',
    'static': 'SUBPACKAGE: client JS (ux-channel.js)',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

