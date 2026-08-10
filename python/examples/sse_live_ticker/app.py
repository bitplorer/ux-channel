"""
SSE auto-tick — live board with zero clicks

Demonstrates uxchannel server push:
  background feeder → ch.refresh(...) → PushBus.publish(topic, result)
  browser EventSource(/ux-channel/push/{topic}) → uidChannel.applyResult(result)

Optional actions: pause / resume / manual tick / change speed.

Run:
  PYTHONPATH=src:/tmp/ux_dom uvicorn examples.sse_live_ticker.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.transport.push import get_push_bus

TOPIC = "public.live.board"
SECRET = "dev-secret-key-32chars-minimum!!!!"


def _state() -> dict[str, Any]:
    s = ch.draft.get("live")
    if not s:
        s = {
            "running": True,
            "interval_s": 1.5,
            "gold": 7450.0,
            "silver": 92.5,
            "ticks": 0,
            "last": "—",
            "history_g": [7450.0] * 20,
            "history_s": [92.5] * 20,
            "status": "live",
        }
        ch.draft.set("live", s)
    return s


def _spark(vals: list[float], color: str, w: int = 200, h: int = 44) -> str:
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(vals):
        x = 2 + i * (w - 4) / max(len(vals) - 1, 1)
        y = h - 2 - (v - lo) / span * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" class="spark">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" points="{" ".join(pts)}"/></svg>'
    )


def _inr(n: float) -> str:
    return f"₹{n:,.2f}"


# channel created after app lifespan needs ch — define ch before regions
# Lifespan will start feeder

ch: Channel  # set below after app factory pattern


class Ticker(Region):
    def render(self, ctx):
        s = _state()
        st = s["status"]
        return f"""
        <div data-channel-id="{self.uid}" class="ticker">
          <div class="badge {st}">{st.upper()}</div>
          <div class="row">
            <div class="cell">
              <div class="lbl">24K Gold</div>
              <div class="px">{_inr(s["gold"])}<small>/g</small></div>
              {_spark(s["history_g"], "#fbbf24")}
            </div>
            <div class="cell">
              <div class="lbl">Silver</div>
              <div class="px">{_inr(s["silver"])}<small>/g</small></div>
              {_spark(s["history_s"], "#94a3b8")}
            </div>
            <div class="cell meta">
              <div class="lbl">SSE ticks</div>
              <div class="px big">{s["ticks"]}</div>
              <div class="sub">last push · {s["last"]}</div>
              <div class="sub">interval · {s["interval_s"]}s · topic <code>{TOPIC}</code></div>
            </div>
          </div>
        </div>
        """


class StatusLine(Region):
    def render(self, ctx):
        s = _state()
        mode = "auto-push via EventSource" if s["running"] else "paused (no server ticks)"
        return f"""
        <div data-channel-id="{self.uid}" class="status">
          <span class="dot {s["status"]}"></span>
          <span>{mode}</span>
          <span class="muted">no button required for live updates</span>
        </div>
        """


def do_tick(*, notice: str | None = None) -> Any:
    """Advance market state and return a refresh Result for push or response."""
    s = _state()
    s["gold"] = max(5000.0, s["gold"] + random.uniform(-22, 25))
    s["silver"] = max(40.0, s["silver"] + random.uniform(-0.9, 1.0))
    s["history_g"] = (s["history_g"] + [s["gold"]])[-20:]
    s["history_s"] = (s["history_s"] + [s["silver"]])[-20:]
    s["ticks"] = int(s["ticks"]) + 1
    s["last"] = datetime.now().strftime("%H:%M:%S")
    s["status"] = "live" if s["running"] else "paused"
    ch.draft.set("live", s)
    r = ch.refresh(ticker, status)
    if notice:
        # append toast without losing morphs
        from ux_channel import Result
        from ux_channel.protocol.ops import toast

        return Result(ok=True, ops=list(r.ops) + [toast(notice)], meta=r.meta)
    return r


def publish_board(result=None) -> int:
    result = result or ch.refresh(ticker, status)
    return get_push_bus().publish(TOPIC, result)


async def feeder_loop(stop: asyncio.Event) -> None:
    """Server-side clock: tick + SSE publish while running."""
    while not stop.is_set():
        s = _state()
        interval = float(s.get("interval_s") or 1.5)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            pass
        s = _state()
        if not s.get("running", True):
            continue
        result = do_tick()
        n = publish_board(result)
        # n == subscribers; 0 is fine when no browser open yet


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(feeder_loop(stop))
    app.state.feeder_stop = stop
    app.state.feeder_task = task
    yield
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=2)
    except Exception:
        task.cancel()


app = FastAPI(title="SSE auto-tick · ux-channel", lifespan=lifespan)
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
    ),
)

ticker = ch.use(Ticker, uid="live.ticker")
status = ch.use(StatusLine, uid="live.status")


@ch.on(name="Live.pause", refresh=[ticker, status])
def pause():
    s = _state()
    s["running"] = False
    s["status"] = "paused"
    ch.draft.set("live", s)
    r = ch.done(notice="Auto-tick paused")
    publish_board(ch.refresh(ticker, status))
    return r


@ch.on(name="Live.resume", refresh=[ticker, status])
def resume():
    s = _state()
    s["running"] = True
    s["status"] = "live"
    ch.draft.set("live", s)
    r = ch.done(notice="Auto-tick resumed")
    publish_board(ch.refresh(ticker, status))
    return r


@ch.on(name="Live.tick", refresh=[ticker, status])
def manual_tick():
    r = do_tick(notice="Manual tick")
    publish_board(r)
    return r


@ch.on(name="Live.faster", refresh=[status, ticker])
def faster():
    s = _state()
    s["interval_s"] = max(0.4, round(float(s["interval_s"]) - 0.3, 2))
    ch.draft.set("live", s)
    r = ch.done(notice=f"Interval {s['interval_s']}s")
    publish_board(ch.refresh(ticker, status))
    return r


@ch.on(name="Live.slower", refresh=[status, ticker])
def slower():
    s = _state()
    s["interval_s"] = min(5.0, round(float(s["interval_s"]) + 0.3, 2))
    ch.draft.set("live", s)
    r = ch.done(notice=f"Interval {s['interval_s']}s")
    publish_board(ch.refresh(ticker, status))
    return r


CSS = """
:root {
  --bg: #0a0e17; --panel: #121a2b; --ink: #e8eefc; --muted: #8b9bb8;
  --line: rgba(148,163,184,.16); --good: #34d399; --warn: #fbbf24; --bad: #fb7185;
  font-family: "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; color: var(--ink);
  background:
    radial-gradient(800px 400px at 0% 0%, #1e1b4b 0%, transparent 50%),
    radial-gradient(700px 360px at 100% 0%, #134e4a 0%, transparent 45%),
    var(--bg);
}
.wrap { max-width: 920px; margin: 0 auto; padding: 1.75rem 1.2rem 3rem; }
h1 { margin: 0 0 .35rem; font-size: 1.65rem; letter-spacing: -.02em; }
.lead { margin: 0 0 1.25rem; color: var(--muted); max-width: 36rem; line-height: 1.5; }
.tags { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .75rem; }
.tags span {
  font-size: .72rem; color: var(--muted); border: 1px solid var(--line);
  padding: .15rem .5rem; border-radius: 999px; background: rgba(0,0,0,.25);
}
.ticker {
  background: linear-gradient(180deg, rgba(255,255,255,.03), transparent), var(--panel);
  border: 1px solid var(--line); border-radius: 18px; padding: 1.1rem 1.2rem 1.2rem;
  box-shadow: 0 20px 50px rgba(0,0,0,.35);
}
.badge {
  display: inline-block; font-size: .68rem; font-weight: 800; letter-spacing: .08em;
  padding: .2rem .55rem; border-radius: 999px; margin-bottom: .75rem;
}
.badge.live { background: rgba(52,211,153,.15); color: var(--good); }
.badge.paused { background: rgba(251,191,36,.12); color: var(--warn); }
.row { display: grid; grid-template-columns: 1.1fr 1.1fr .9fr; gap: .85rem; }
@media (max-width: 720px) { .row { grid-template-columns: 1fr; } }
.cell {
  background: rgba(0,0,0,.22); border: 1px solid var(--line);
  border-radius: 14px; padding: .85rem 1rem;
}
.lbl { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.px { font-size: 1.45rem; font-weight: 800; font-variant-numeric: tabular-nums; margin: .25rem 0; }
.px.big { font-size: 2rem; color: #a5b4fc; }
.px small { font-size: .8rem; color: var(--muted); font-weight: 600; }
.sub { font-size: .78rem; color: var(--muted); margin-top: .2rem; }
.sub code { color: #c7d2fe; }
.spark { display: block; margin-top: .35rem; }
.status {
  margin-top: .9rem; display: flex; flex-wrap: wrap; align-items: center; gap: .55rem;
  font-size: .9rem;
}
.dot {
  width: .55rem; height: .55rem; border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(52,211,153,.5);
}
.dot.live { background: var(--good); animation: pulse 1.5s infinite; }
.dot.paused { background: var(--warn); }
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(52,211,153,.5); }
  70% { box-shadow: 0 0 0 8px rgba(52,211,153,0); }
  100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}
.muted { color: var(--muted); font-size: .82rem; }
.toolbar { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: 1rem; }
button {
  appearance: none; cursor: pointer; border: 1px solid var(--line);
  background: rgba(255,255,255,.05); color: var(--ink);
  border-radius: 999px; padding: .5rem .95rem; font-weight: 600; font-size: .86rem;
}
button:hover { border-color: rgba(129,140,248,.45); background: rgba(129,140,248,.12); }
button.primary { background: linear-gradient(135deg,#6366f1,#4f46e5); border-color: transparent; }
.arch {
  margin-top: 1.5rem; font-size: .8rem; color: var(--muted);
  background: rgba(0,0,0,.25); border: 1px solid var(--line);
  border-radius: 12px; padding: .85rem 1rem; line-height: 1.55;
}
.arch code { color: #c7d2fe; }
.log {
  margin-top: .85rem; font-family: ui-monospace, monospace; font-size: .75rem;
  color: var(--muted); max-height: 5.5rem; overflow: auto;
  border-left: 2px solid var(--line); padding-left: .75rem;
}
"""

SSE_JS = """
<script>
document.addEventListener('uid:push', function (ev) {
  var logEl = document.getElementById('sse-log');
  if (!logEl || !ev.detail) return;
  var r = ev.detail.result || {};
  var n = (r.ops || []).filter(function (o) { return o.op === 'morph'; }).length;
  var line = document.createElement('div');
  line.textContent = new Date().toLocaleTimeString() + '  push · morphs=' + n;
  logEl.prepend(line);
  while (logEl.children.length > 12) logEl.removeChild(logEl.lastChild);
});
document.addEventListener('DOMContentLoaded', function () {
  var logEl = document.getElementById('sse-log');
  if (logEl) {
    var line = document.createElement('div');
    line.textContent = 'auto-subscribe via data-channel-push-topic (ux-channel.js EventSource)';
    logEl.prepend(line);
  }
});
</script>
"""


def _btn(label: str, action, *, primary: bool = False) -> str:
    d = ch.control(action).as_dict()
    attrs = " ".join(f'{k}="{v}"' for k, v in d.items())
    cls = "primary" if primary else ""
    return f'<button type="button" class="{cls}" {attrs}>{label}</button>'


@app.get("/", response_class=HTMLResponse)
def index():
    scripts = str(demo_scripts(ch, ))
    body = f"""
<div class="wrap">
  <div class="tags">
    <span>ux-channel</span><span>SSE push</span><span>auto-tick</span><span>no click required</span>
  </div>
  <h1>SSE live ticker</h1>
  <p class="lead">
    Server feeder publishes <code>Result</code> morphs on topic
    <code>{TOPIC}</code>. The browser only listens —
    <code>EventSource</code> → <code>uidChannel.applyResult</code>.
  </p>
  {ticker()}
  {status()}
  <div class="toolbar">
    {_btn("Pause", pause)}
    {_btn("Resume", resume, primary=True)}
    {_btn("Manual tick", manual_tick)}
    {_btn("Faster", faster)}
    {_btn("Slower", slower)}
  </div>
  <div id="sse-log" class="log" aria-live="polite"></div>
  <div class="arch">
    <strong>Flow</strong><br/>
    <code>feeder_loop</code> → <code>do_tick()</code> → <code>ch.refresh(live.ticker, live.status)</code>
    → <code>PushBus.publish("{TOPIC}", result)</code><br/>
    → <code>GET /ux-channel/push/{TOPIC}</code> (SSE)<br/>
    → <code>uidChannel.applyResult(result)</code> (same ops as a click)
  </div>
</div>
"""
    try:
        from ux_dom import Document
        from ux_dom.dom import raw

        doc = Document(
            head=[
                raw('<meta charset="utf-8">'),
                raw('<meta name="viewport" content="width=device-width,initial-scale=1">'),
                raw("<title>SSE auto-tick</title>"),
                raw(f"<style>{CSS}</style>"),
                raw(scripts),
                raw(SSE_JS),
            ]
        )
        html = str(doc(raw(body)))
        if "<body" in html:
            html = html.replace("<body", f"<body {attr_string(ch.body_attrs(push_topic=TOPIC))}", 1)
        else:
            html = f"<!doctype html><html><body {attr_string(ch.body_attrs(push_topic=TOPIC))}>{html}</body></html>"
        return HTMLResponse(html)
    except ImportError:
        return HTMLResponse(
            f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SSE auto-tick</title><style>{CSS}</style>{scripts}{SSE_JS}</head>
<body {attr_string(ch.body_attrs(push_topic=TOPIC))}>{body}</body></html>"""
        )


@app.get("/health")
def health():
    s = _state()
    return {
        "ok": True,
        "topic": TOPIC,
        "running": s["running"],
        "ticks": s["ticks"],
        "subscribers": len(getattr(get_push_bus().backend, "_subs", {}).get(TOPIC, ())),
    }
