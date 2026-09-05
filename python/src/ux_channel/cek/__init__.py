"""CEK adapter — Channel product over cek-runtime Host (cut #2).

Channel stays the product (regions, classic IR, FastAPI). Kernel SSoT is
**cek-runtime** ([ADR 0008](../../../../SPEC/architecture/ADR/0008-cek-runtime-kernel-ssot.md)).
The ``[cek]`` extra is a drop-in wrap, not a second kernel.

off      today's path. Zero cek imports.
adapt    extra ``[cek]``; Host on the side; Channel Cap remains authority.
require  mint/verify/once/sealed-args go through cek-runtime Host
         (``RustHostKernel`` / ``cek host-json`` when CEK_BIN is the runtime
         binary, else the documented port ``cek_host.Host``).

``cek_surface`` is Continuation compose only — not a kernel.
Classic Result.ops stay Channel wire. EffectGraph is L7 pre-project after
Cap only. ``flow_id`` maps to ``trace`` (correlation). hello/stamps encode
as Profile/Manifest handshake — Manifest never grants Cap.
"""

from __future__ import annotations

from ux_channel.cek.config import CEK_MODES, cek_available, parse_cek

__all__ = [
    "CEK_MODES",
    "parse_cek",
    "cek_available",
]
