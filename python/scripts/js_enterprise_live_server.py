"""Enterprise live-DOM harness: multi-region, bridges, caps, concurrent actions."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import ConfettiBridge, CountUpBridge
from ux_channel.render.kit import attr_string, demo_scripts

app = FastAPI(title="js-enterprise-live")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="enterprise-live-dom-secret-key-32b!",
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        webrtc_require_ticket=False,
    ),
)

S = {"a": 0, "b": 0, "c": 0, "hits": 0}
fx = ConfettiBridge(ch)("fx1")
cu = CountUpBridge(ch)("cu1", value=0)


@ch.region("panel_a")
def panel_a(ctx) -> str:
    return (
        f'<section id="panel_a" data-channel-id="panel_a" class="panel" data-panel="a">'
        f'<h2>A</h2><strong class="val">{S["a"]}</strong>'
        f'<span data-keep-a="1">keep-a</span></section>'
    )


@ch.region("panel_b")
def panel_b(ctx) -> str:
    return (
        f'<section id="panel_b" data-channel-id="panel_b" class="panel" data-panel="b">'
        f'<h2>B</h2><strong class="val">{S["b"]}</strong>'
        f'<span data-keep-b="1">keep-b</span></section>'
    )


@ch.region("panel_c")
def panel_c(ctx) -> str:
    return (
        f'<section id="panel_c" data-channel-id="panel_c" class="panel" data-panel="c">'
        f'<h2>C</h2><strong class="val">{S["c"]}</strong>'
        f'<div data-channel-id="panel_c_note" id="panel_c_note">note={S["c"]}</div>'
        f"</section>"
    )


@ch.region("panel_c_note")
def panel_c_note(ctx) -> str:
    return f'<div data-channel-id="panel_c_note" id="panel_c_note">note={S["c"]}</div>'


@ch.on
def bump_a(sku: str = "X") -> object:
    S["a"] += 1
    S["hits"] += 1
    return ch.done(refresh=["panel_a"], notice=f"a={S['a']}")


@ch.on
def bump_b(sku: str = "X") -> object:
    S["b"] += 1
    S["hits"] += 1
    return ch.done(refresh=["panel_b"], notice=f"b={S['b']}")


@ch.on
def bump_c(sku: str = "X") -> object:
    S["c"] += 1
    S["hits"] += 1
    return ch.done(refresh=["panel_c_note"], notice=f"c={S['c']}")


@ch.on
def bump_all(sku: str = "X") -> object:
    S["a"] += 1
    S["b"] += 1
    S["c"] += 1
    S["hits"] += 1
    try:
        return cu.set_value(S["a"] + S["b"] + S["c"]).merge(
            ch.done(refresh=["panel_a", "panel_b", "panel_c"], notice="all")
        )
    except Exception:
        return ch.done(refresh=["panel_a", "panel_b", "panel_c"], notice="all")


@ch.on
def boom() -> object:
    S["hits"] += 1
    return fx.burst()


@app.get("/api/state")
def state():
    return dict(S)


def _host(island) -> str:
    from ux_channel.render.html import attr_escape

    attrs = island.mount_spec().attrs
    parts = [f'{k}="{attr_escape(str(v))}"' for k, v in attrs.items()]
    return f'<div {" ".join(parts)} class="bridge-host" style="min-height:5rem;position:relative"></div>'


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    ba = ch.control(bump_a, trust_sku="X")
    bb = ch.control(bump_b, trust_sku="X")
    bc = ch.control(bump_c, trust_sku="X")
    ball = ch.control(bump_all, trust_sku="X")
    bboom = ch.control(boom)
    scripts = demo_scripts(ch)
    if "ux-bridge.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/ux-bridge.js" defer></script>'
    if "builtins.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/adapters/builtins.js" defer></script>'
    if "widgets.js" not in scripts:
        scripts += '\n<script src="/ux-channel/static/adapters/widgets.js" defer></script>'
    body = attr_string(ch.body_attrs())
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>Enterprise Live DOM</title>
{scripts}
<style>
body{{font-family:system-ui;margin:1rem;background:#0b1220;color:#e2e8f0}}
.row{{display:flex;gap:1rem;flex-wrap:wrap}}
.panel{{background:#111827;padding:1rem;border-radius:12px;min-width:10rem}}
button{{margin:.25rem;padding:.5rem .9rem;border:0;border-radius:8px;background:#38bdf8;color:#0b1220;font-weight:600;cursor:pointer}}
.bridge-host{{background:#0f172a;border-radius:8px;margin-top:.5rem}}
#static-siblings p{{opacity:.8}}
</style>
</head>
<body {body}>
<h1>Enterprise live DOM</h1>
<p id="status">multi-region · bridges · caps · channel header</p>
<div class="row">
  {panel_a(None)}
  {panel_b(None)}
  {panel_c(None)}
</div>
<div class="row" style="margin-top:1rem">
  <button type="button" id="ba" {ba}>Bump A</button>
  <button type="button" id="bb" {bb}>Bump B</button>
  <button type="button" id="bc" {bc}>Bump C note</button>
  <button type="button" id="ball" {ball}>Bump all</button>
  <button type="button" id="boom" {bboom}>Boom</button>
</div>
<div class="row" style="margin-top:1rem;width:100%">
  <div style="flex:1"><div>confetti</div>{_host(fx)}</div>
  <div style="flex:1"><div>countup</div>{_host(cu)}</div>
</div>
<div id="static-siblings">
  <p data-keep="1">sibling-1</p>
  <p data-keep="1">sibling-2</p>
  <p data-keep="1">sibling-3</p>
</div>
</body></html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8768, log_level="warning")
