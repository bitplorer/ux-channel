"""
Canonical uxchannel + ux-dom-style app (0.1 production shape).

  uvicorn examples.canonical_ux_dom.app:app --host 0.0.0.0 --port 8080

Shows: Region + @Region.action + ch.control(trust_*) + live bind/publish
+ production-oriented config (memory stores OK for single-worker demo).
"""

from __future__ import annotations

import asyncio
import os
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

app = FastAPI(title="uxchannel canonical")
# Single-worker demo: allow_memory_stores. Multi-worker: with_redis(REDIS_URL).
_secret = os.environ.get("UX_CHANNEL_SECRET", "dev-secret-key-32chars-minimum!!!!")
if os.environ.get("REDIS_URL"):
    cfg = ChannelConfig.production(_secret).with_redis(os.environ["REDIS_URL"])
else:
    cfg = ChannelConfig.development(secret=_secret)
ch = Channel.boot(app, config=cfg)


class Ticker(Region):
    uid = "canon.ticker"

    def render(self, ctx=None):
        n = int(self.state_get("n", 0) or 0)
        return f'<div class="card"><h2>Ticker</h2><p class="val">{n}</p></div>'

    @Region.action(broadcast="public.canon")
    def bump(self):
        self.state_change("n", lambda x: int(x or 0) + 1, default=0)


class Status(Region):
    uid = "canon.status"

    def render(self, ctx=None):
        raw = ch.draft.get("region:canon.ticker")
        n = (raw or {}).get("n", 0) if isinstance(raw, dict) else 0
        return f'<div class="card muted">Live status · n={n}</div>'


ticker = Ticker(ch).mount()
status = Status(ch).mount()
ch.live.bind("public.canon", ticker, status)


@app.on_event("startup")
async def _feeder():
    async def loop():
        while True:
            await asyncio.sleep(2.5)
            # simulate external tick without client click
            try:
                ticker.state_change("n", lambda x: int(x or 0) + random.choice([0, 0, 1]), default=0)
                ch.live.publish("public.canon")
            except Exception:
                pass
    asyncio.create_task(loop())


@app.get("/")
def index():
    body = attr_string(ch.body_attrs(
        ws=True,
        push_topic="public.canon",
    ))
    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>uxchannel canonical</title>
<style>
  :root {{ font-family: system-ui,sans-serif; color:#0f172a; background:#f8fafc; }}
  body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem; }}
  .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; margin:.75rem 0; }}
  .val {{ font-size:2rem; font-weight:700; }}
  .muted {{ color:#64748b; font-size:.95rem; }}
  button {{ background:#0f172a; color:#fff; border:0; border-radius:8px; padding:.6rem 1rem; cursor:pointer; }}
  code {{ background:#e2e8f0; padding:.1rem .35rem; border-radius:4px; }}
</style>
{demo_scripts(ch, )}
</head>
<body {body}>
  <h1>Canonical board</h1>
  <p>Prefer <code>@Region.action</code> + <code>ch.control</code> + <code>ch.live</code>.</p>
  {ticker()}
  {status()}
  <p><button type="button" {ch.control(ticker.bump)}>Bump</button></p>
</body></html>"""
    return HTMLResponse(html)
