"""ch.media plugin demo — mesh by default; set LIVEKIT_* for SFU."""

from __future__ import annotations

import os
from dataclasses import replace

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.render.kit import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

secret = os.environ.get("UX_CHANNEL_SECRET", "media-bridge-dev-secret-key-32ch!")
cfg = ChannelConfig.development(
    secret=secret,
    allow_memory_stores=True,
    webrtc_enabled=True,
)
if os.environ.get("LIVEKIT_URL"):
    cfg = replace(
        cfg,
        sfu_provider="livekit",
        sfu_url=os.environ["LIVEKIT_URL"],
        sfu_api_key=os.environ.get("LIVEKIT_API_KEY", ""),
        sfu_api_secret=os.environ.get("LIVEKIT_API_SECRET", ""),
    )

app = FastAPI(title="media bridge")
ch = Channel.boot(app, config=cfg)


@app.get("/health")
def health():
    return ch.media.diagnose()


@app.get("/", response_class=HTMLResponse)
def index():
    p = ch.media.plugin("lobby", sub="demo-user")
    # Host-owned minimal shell — not library UI chrome
    return HTMLResponse(
        f"""<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>media bridge</title>
{script_tags(p)}
</head>
<body {attr_string(p)} style="font-family:system-ui;background:#0a0a0c;color:#eee;padding:1.5rem">
  <h1>ch.media · {p.mode}/{p.provider}</h1>
  <p>Plugin bag only. Attach tracks in the host.</p>
  <video data-channel-media-local autoplay playsinline muted style="max-width:100%;background:#000"></video>
  <video data-channel-media-remote autoplay playsinline style="max-width:100%;background:#000"></video>
  <pre style="opacity:.7;font-size:12px">{p.client_json[:200]}…</pre>
</body></html>"""
    )
