"""Zone / package: **paint**

HTML safety, morph IR, placement — how UI reaches the client.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'paint'
DESCRIPTION = 'HTML safety, morph IR, placement — how UI reaches the client.'
MEMBERS = {'demo': 'Demo / SSR HTML adapters — **the only module that emits markup strings**.', 'html': 'HTML wiring helpers — attributes and demo tags, not a design system.', 'html_document': 'Document / runtime **Placement** for Channel (no HTML strings).', 'html_safe': 'HTML escaping helpers (SafeHtml, esc, mark_safe) for channel render paths.', 'morph_ir': 'Morph IR — host-agnostic UI structure for multi-surface projection.', 'placement': 'Placement — framework-agnostic **data** (one source of truth).', 'projections': 'Multi-surface projections from Morph IR.', 'render': "HtmlRenderer protocol — turn *any* library's values into HTML fragments.", 'response': 'FastAPI / Starlette HTML responses — ux-dom-compatible.', 'slot_compile': 'Stable slot/uid compile from host-agnostic tree dicts.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
