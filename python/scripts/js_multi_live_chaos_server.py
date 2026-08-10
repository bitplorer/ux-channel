"""Live multi-JS page: channel + bridge + fx + ui + inspector + webrtc + controls."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import ConfettiBridge, CountUpBridge
from ux_channel.paint.demo import attr_string, demo_scripts

app = FastAPI(title="js-multi-live-chaos")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="js-multi-live-chaos-secret-key-32b!",
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        webrtc_require_ticket=False,
    ),
)

STATE = {"n": 0, "hits": 0}

confetti_fac = ConfettiBridge(ch)
countup_fac = CountUpBridge(ch)
# islands registered once
fx_island = confetti_fac("fx1")
cu_island = countup_fac("cu1", value=0)


@ch.on
def bump(sku: str = "X") -> object:
    STATE["n"] += 1
    STATE["hits"] += 1
    # update countup display via bridge update ops when possible
    try:
        return cu_island.set_value(STATE["n"]).merge(
            ch.done(notice=f"n={STATE['n']}", refresh=["counter", "hits"])
        )
    except Exception:
        return ch.done(notice=f"n={STATE['n']}", refresh=["counter", "hits"])


@ch.on
def boom() -> object:
    return fx_island.burst()


@ch.region("counter")
def counter_region(ctx) -> str:
    return f'<div id="counter" data-channel-id="counter">{STATE["n"]}</div>'


@ch.region("hits")
def hits_region(ctx) -> str:
    return f'<div id="hits" data-channel-id="hits">{STATE["hits"]}</div>'


def _host_html(island) -> str:
    """HTML host node with hyphenated data-channel-bridge-* attrs (escaped props)."""
    spec = island.mount_spec()
    attrs = dict(spec.attrs)
    parts = []
    for k, v in attrs.items():
        # attrs already use data-channel-bridge-* keys with JSON string values
        from ux_channel.paint.html import attr_escape

        parts.append(f'{k}="{attr_escape(str(v))}"')
    return f'<div {" ".join(parts)} class="bridge-host" style="position:relative;min-height:6rem"></div>'


def _page(*, double_channel: bool = False) -> str:
    ctrl = ch.control(bump, trust_sku="X")
    boom_ctrl = ch.control(boom)
    body = attr_string(ch.body_attrs())
    scripts = demo_scripts(ch)
    if "ux-bridge.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/ux-bridge.js" defer id="ux-bridge"></script>'
    if "ux-fx.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/adapters/ux-fx.js" defer id="ux-fx"></script>'
    if "ux-ui.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/adapters/ux-ui.js" defer id="ux-ui"></script>'

    double = ""
    if double_channel:
        double = (
            '\n<script src="/ux-channel/static/ux-channel.js" defer id="ux-channel-dup"></script>'
            '\n<script src="/ux-channel/static/ux-bridge.js" defer id="ux-bridge-dup"></script>'
            '\n<script src="/ux-channel/static/adapters/ux-fx.js" defer id="ux-fx-dup"></script>'
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Multi-JS Live Chaos</title>
{scripts}
{double}
<style>
  body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #0b1220; color: #e2e8f0; }}
  .row {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
  .card {{ background: #111827; border-radius: 12px; padding: 1rem; min-width: 12rem; }}
  button {{ padding: .55rem 1rem; border-radius: 8px; border: 0; background: #38bdf8; color: #0b1220; font-weight: 600; cursor: pointer; }}
  .bridge-host {{ background: #0f172a; border-radius: 8px; margin-top: .5rem; }}
</style>
</head>
<body {body}>
  <h1>Multi-JS live chaos</h1>
  <p id="status">channel + bridge + fx + ui + inspector + webrtc</p>
  <div class="row">
    <div class="card">
      <div>counter</div>
      {counter_region(None)}
      <div>hits</div>
      {hits_region(None)}
      <button type="button" id="bump" {ctrl}>Bump</button>
      <button type="button" id="boom" {boom_ctrl}>Boom</button>
    </div>
    <div class="card" style="flex:1">
      <div>confetti host</div>
      {_host_html(fx_island)}
      <div>countup host</div>
      {_host_html(cu_island)}
    </div>
  </div>
  <div id="static-siblings">
    <p data-keep="1">sibling A</p>
    <p data-keep="1">sibling B</p>
  </div>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(_page(double_channel=False))


@app.get("/double", response_class=HTMLResponse)
def double() -> HTMLResponse:
    return HTMLResponse(_page(double_channel=True))


@app.get("/wrong-order", response_class=HTMLResponse)
def wrong_order() -> HTMLResponse:
    body = attr_string(ch.body_attrs())
    html = f"""<!doctype html>
<html><head>
<script src="/ux-channel/static/adapters/ux-fx.js"></script>
<script src="/ux-channel/static/ux-bridge.js"></script>
<script src="/ux-channel/static/adapters/ux-fx.js"></script>
<script src="/ux-channel/static/ux-channel.js"></script>
<title>wrong order</title>
</head>
<body {body}>
  <h1 id="ok">still alive</h1>
  <div data-channel-bridge-id="c1" data-channel-bridge-package="ux-fx/confetti"
       style="min-height:4rem"></div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/api/state")
def api_state():
    return dict(STATE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8767, log_level="warning")
