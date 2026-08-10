"""
Minimal FastAPI app for soak targets.

WHY: harness must not depend on example apps; one factory = reproducible SLOs.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Result, toast


def build_soak_app(
    *,
    secret: str | None = None,
    redis_url: str | None = None,
    webrtc_require_ticket: bool = True,
    webrtc_max_peers: int = 32,
    whip_enabled: bool = False,
) -> tuple[FastAPI, Channel]:
    """
    Build Channel.boot app with soak-friendly defaults.

    * Tickets on by default (production door)
    * Same-origin relaxed for scripted clients
    * Optional Redis for multi-worker RTC store
    """
    secret = secret or os.environ.get(
        "SOAK_SECRET", "soak-test-secret-key-32chars-min!!"
    )
    redis_url = redis_url or os.environ.get("REDIS_URL") or None

    kwargs: dict[str, Any] = {
        "allow_memory_stores": True,
        "enforce_same_origin": False,
        "require_channel_header": False,
        "webrtc_enabled": True,
        "webrtc_require_ticket": webrtc_require_ticket,
        "webrtc_require_origin": False,
        "webrtc_max_peers": webrtc_max_peers,
        "webrtc_use_redis": bool(redis_url) or None,
        "whip_enabled": whip_enabled,
        "rate_limit_per_minute": 0,
    }
    if redis_url:
        kwargs["redis_url"] = redis_url

    # development keeps weak-secret ergonomics for local; production-like tickets
    cfg = ChannelConfig.development(secret=secret, **kwargs)
    # force ticket flag even in development when requested
    object.__setattr__(cfg, "webrtc_require_ticket", webrtc_require_ticket)

    app = FastAPI(title="ux-channel-soak", version="0.1.0")
    ch = Channel.boot(app, config=cfg)

    @ch.region
    def soak_badge(ctx):  # type: ignore[no-untyped-def]
        n = int(ch.draft.get("n", 0) or 0)
        return f'<b data-channel-id="soak_badge">{n}</b>'

    @ch.on(refresh=[soak_badge], idempotent=False)
    def soak_inc():  # type: ignore[no-untyped-def]
        ch.draft.set("n", int(ch.draft.get("n", 0) or 0) + 1)

    @ch.on(idempotent=True)
    def soak_ping():  # type: ignore[no-untyped-def]
        return Result.success(toast("pong"))

    @app.get("/health")
    def health():  # type: ignore[no-untyped-def]
        return {
            "ok": True,
            "webrtc": ch.webrtc.diagnose(),
            "n": ch.draft.get("n", 0),
        }

    # expose channel for harness ticket minting in inline mode
    app.state.soak_channel = ch  # type: ignore[attr-defined]
    return app, ch
