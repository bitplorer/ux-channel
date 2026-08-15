"""CEK drop-in adapter (Phase 1).

Channel consumes cek-host + cek-surface via this package. It does **not**
vendor-copy them. Default ``ChannelConfig.cek = "off"`` imports nothing.

Modes
-----
off      today's path. Zero new imports. CI main.
adapt    extra ``[cek]`` installed; adapter live; Channel Cap remains authority.
require  Cap mint/verify/once/sealed-args + enhance compose go through cek.

Invariant 11 (D4): cek-surface never imports ux_channel.
Invariant 13: ux_channel.CapService is still the off-path machine.
The require path wraps the same registry slot; it does not grow root ``__all__``.
"""

from __future__ import annotations

from ux_channel.cek.config import CEK_MODES, cek_available, parse_cek

__all__ = [
    "CEK_MODES",
    "parse_cek",
    "cek_available",
]
