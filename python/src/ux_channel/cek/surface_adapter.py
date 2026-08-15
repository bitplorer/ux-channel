"""enhance façade → cek_surface when ChannelConfig.cek=require.

Phase 1: native enhance code still exists behind off.
Handshake /hello is adapt-or-require only — classic IR 0.1 never needs it.

KEEP in Channel (no cek twin): PeerHello, causal Trace, delta, recorder, ASGI.
REPLACE (behind require): Continuation type + match/resolve.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from ux_channel.cek.config import parse_cek, require_cek_installed

log = logging.getLogger("ux_channel.cek.surface_adapter")


def uses_cek_surface(config: Any) -> bool:
    mode = parse_cek(getattr(config, "cek", "off") if config is not None else "off")
    return mode == "require"


def continuation_namespace(config: Any) -> Any:
    """Return the Continuation module to use for this config.

    require → cek_surface.continuation (after extra check)
    off/adapt → ux_channel.enhance.continuations (native clone)
    """
    mode = parse_cek(getattr(config, "cek", "off") if config is not None else "off")
    if mode != "require":
        from ux_channel.enhance import continuations as native

        return native
    require_cek_installed(mode)
    import cek_surface.continuation as cek_cont

    return cek_cont


def to_channel_continuation(raw: Any) -> dict[str, Any]:
    """Normalize a cek or native Continuation to the Channel envelope dict.

    Classic clients ignore unknown keys. ``once`` / ``meta`` stay Channel-only.
    """
    if hasattr(raw, "to_dict"):
        body = dict(raw.to_dict())
    elif isinstance(raw, Mapping):
        body = dict(raw)
    else:
        raise TypeError(f"not a continuation: {type(raw)!r}")
    # Accept both store:KEY (cek) and store.KEY (Channel native).
    args_from = dict(body.get("args_from") or {})
    norm: dict[str, str] = {}
    for k, v in args_from.items():
        s = str(v)
        if s.startswith("store:"):
            s = "store." + s[6:]
        elif s.startswith("event:"):
            s = "event." + s[6:]
        norm[str(k)] = s
    if norm:
        body["args_from"] = norm
    return body
