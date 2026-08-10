"""CORS helper for browser apps that call Channel from a separate frontend origin.

WHY
---
Same-origin is the default (enforce_same_origin). SPAs on another origin need
CORS *and* an explicit allowed_origins list on ChannelConfig.

::

    from ux_channel.transport.cors import apply_cors
    apply_cors(app, origins=[\"https://app.example.com\"], path_prefix=\"/ux-channel\")"""

from __future__ import annotations

from typing import Any, Sequence


def apply_cors(
    app: Any,
    *,
    origins: Sequence[str],
    path_prefix: str = "/ux-channel",
    allow_credentials: bool = True,
    allow_methods: Sequence[str] = ("GET", "POST", "OPTIONS", "DELETE"),
    allow_headers: Sequence[str] = (
        "Content-Type",
        "Accept",
        "Authorization",
        "X-Channel",
        "X-Channel-Agent-Token",
        "X-Channel-Agent-Id",
        "X-Request-Id",
    ),
) -> Any:
    """
    Attach Starlette CORSMiddleware scoped via allow_origins.

    Also recommend setting ChannelConfig.allowed_origins to the same list and
    enforce_same_origin=False when using cross-origin SPAs.
    """
    try:
        from starlette.middleware.cors import CORSMiddleware
    except ImportError as exc:  # pragma: no cover
        raise ImportError("starlette required for apply_cors") from exc

    origins_list = [o for o in origins if o]
    if not origins_list:
        raise ValueError("origins must be non-empty")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins_list),
        allow_credentials=allow_credentials,
        allow_methods=list(allow_methods),
        allow_headers=list(allow_headers),
    )
    # stash for hosts that want to read it
    try:
        app.state.ux_channel_cors_origins = list(origins_list)  # type: ignore[attr-defined]
    except Exception:
        pass
    return app
