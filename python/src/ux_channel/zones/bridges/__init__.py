"""Zone / package: **bridges**

SUBPACKAGE: npm island presets.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'bridges'
DESCRIPTION = 'SUBPACKAGE: npm island presets.'
MEMBERS = {'_factory': 'Shared factory + commit helpers for bridge presets.', 'aurora': 'Aurora / mesh-gradient background bridge — cinematic full-bleed motion.', 'chartjs': 'Chart.js **bridge preset** — data-first, no HTML.', 'codemirror': 'CodeMirror 6-style editor bridge (CDN adapter) — code UIs for ux-dom.', 'confetti': 'Confetti effect bridge — celebration bursts without writing canvas code.', 'countup': 'Count-up / metric ticker bridge — animated numbers for dashboards.', 'datepicker': 'Flatpickr date/time bridge — scheduling and forms.', 'generic': 'Generic island bridge — wrap **any** npm / adapter package for any HTML host.', 'leaflet': 'Leaflet map bridge — high-value for location UIs (ux-dom host).', 'lottie': 'Lottie animation bridge — stunning motion from JSON/CDN.', 'mermaid': 'Mermaid diagram bridge — architecture & flow diagrams in ux-dom.', 'particles': 'Particle field bridge — ambient interactive particles for hero UIs.', 'quill': 'Quill rich-text bridge — documents and comments.', 'select': 'Searchable select bridge (Tom Select-compatible adapter) — forms that feel nativ', 'sortable': 'SortableJS list bridge — drag-and-drop reordering for ux-dom lists.', 'spotlight': 'Spotlight / glass-glow hover effect for premium card UIs.', 'swiper': 'Swiper carousel bridge — galleries and marketing carousels.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
