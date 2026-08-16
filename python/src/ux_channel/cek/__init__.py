"""CEK adapter — Channel product over cek-host 0.1.3 + cek-surface 0.1.3.

Channel stays the product (regions, classic IR, FastAPI). cek-host is the
Cap/decide machine when ``ChannelConfig.cek = require``. cek-surface is
Continuation compose only. Nothing is vendored.

off      today's path. Zero cek imports.
adapt    extra ``[cek]``; Host on the side; Channel Cap remains authority.
require  mint/verify/once/sealed-args go through ``cek_host.Host``.

Classic Result.ops (morph/toast/navigate) stay Channel wire. S pairs
(``kv.*`` ``log.append`` ``ui.dom.morph|restore``) are the only thing
``Host.project_wire`` will accept — see ``cek.project``.
"""

from __future__ import annotations

from ux_channel.cek.config import CEK_MODES, cek_available, parse_cek

__all__ = [
    "CEK_MODES",
    "parse_cek",
    "cek_available",
]
