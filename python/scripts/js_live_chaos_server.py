"""Minimal live app for JS chaos — serve stock ux-channel.js + one control."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.demo import attr_string, demo_scripts

app = FastAPI(title="js-live-chaos")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="js-live-chaos-secret-key-32bytes!!",
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
    ),
)

COUNTER = {"n": 0}


@ch.on
def bump(sku: str = "X") -> object:
    COUNTER["n"] += 1
    return ch.done(notice=f"n={COUNTER['n']}", refresh=["counter"])


@ch.region("counter")
def counter_region(ctx) -> str:
    return f'<div id="counter" data-channel-id="counter">{COUNTER["n"]}</div>'


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    # str(ControlAttrs) HTML-escapes JSON args — required for live JS
    ctrl = ch.control(bump, trust_sku="X")
    tags = demo_scripts(ch)
    body = attr_string(ch.body_attrs())
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>JS Live Chaos</title>
{tags}
</head>
<body {body}>
  <h1>JS live chaos</h1>
  {counter_region(None)}
  <button type="button" id="bump" {ctrl}>Bump</button>
  <p id="hint">require_channel_header + cap + stock ux-channel.js</p>
</body></html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
