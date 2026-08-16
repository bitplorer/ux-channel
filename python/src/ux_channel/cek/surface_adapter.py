"""enhance façade → cek_surface when ChannelConfig.cek=require.

Handshake /hello, causal, delta, recorder stay Channel-native.
Continuation type + match/resolve come from cek_surface on require.
``Surface.arm`` is available via ``arm()``; Channel still mints the Cap.
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
    """require → cek_surface.continuation; else Channel native."""
    mode = parse_cek(getattr(config, "cek", "off") if config is not None else "off")
    if mode != "require":
        from ux_channel.enhance import continuations as native

        return native
    require_cek_installed(mode)
    import cek_surface.continuation as cek_cont

    return cek_cont


def arm(
    host: Any,
    event: str,
    action: str,
    *,
    once: bool = True,
    args_from: Mapping[str, str] | None = None,
    static_args: Mapping[str, Any] | None = None,
) -> Any:
    """Mint a continuation Cap the way Surface.arm does. Host still verifies."""
    from cek_surface.surface import Surface

    s = Surface(kernel=host, carrier_kind="memory")
    return s.arm(
        event,
        action,
        once=once,
        args_from=dict(args_from) if args_from else None,
        static_args=dict(static_args) if static_args else None,
    )


def to_channel_continuation(raw: Any) -> dict[str, Any]:
    """Normalize a cek or native Continuation to the Channel envelope dict."""
    if hasattr(raw, "to_dict"):
        body = dict(raw.to_dict())
    elif isinstance(raw, Mapping):
        body = dict(raw)
    else:
        raise TypeError(f"not a continuation: {type(raw)!r}")
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
