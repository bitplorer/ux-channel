"""Full-surface live harness for ground-up library checks."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.demo import demo_button, demo_page
from ux_channel.dx_dashboard import build_dashboard_model, render_dashboard_html
from ux_channel.otel import attach_otel, dashboard_snapshot, setup_otel, status as otel_status
from ux_channel.trace import TraceConfig, get_tracer

app = FastAPI(title="ux-channel live full harness")
cfg = ChannelConfig.development(
    secret="live-full-harness-secret-key-32ch!!",
    allow_memory_stores=True,
    observe="otel",
    require_cap=False,
)
ch = Channel.boot(app, config=cfg)

get_tracer().configure(TraceConfig(enabled=True, retain=200, capture_payloads=False))
setup_otel(service_name="ux_channel_live_full")
attach_otel()


def counter_html(n: int) -> str:
    return (
        f'<div id="Counter:root" data-channel-id="Counter:root" '
        f'style="display:flex;gap:.75rem;align-items:center">'
        f'<strong id="count">{n}</strong>'
        f'{demo_button(ch, "+", "Counter.inc", trust={"n": n}, target="Counter:root")}'
        f'{demo_button(ch, "boom", "Counter.boom", trust={"n": n})}'
        f"</div>"
    )


@ch.region("counter")
def counter(ctx):
    n = int(ch.draft.get("n", 0) or 0)
    return counter_html(n)


@ch.on("Counter.inc", refresh=[counter], idempotent=False)
def counter_inc():
    ch.draft.set("n", int(ch.draft.get("n", 0) or 0) + 1)


@ch.on("Counter.boom")
def counter_boom():
    return ch.fail.valid(
        {"n": ["cannot boom"]},
        region="Counter:root",
        html=counter_html(int(ch.draft.get("n", 0) or 0)),
        message="validation demo",
        notice=True,
    )


@ch.on("Echo")
def echo(msg: str = "hi"):
    return ch.done(notice=f"echo:{msg}")


@app.get("/", response_class=HTMLResponse)
def index():
    body = demo_page(
        ch,
        "<h1>ux-channel live full harness</h1>",
        "<p>Brand: PyPI ux-channel · import ux_channel · CLI uxchannel</p>",
        ch.regions.html("counter"),
        demo_button(ch, "Echo", "Echo", args={"msg": "live"}),
        title="live-full",
        bridge=True,
    )
    return HTMLResponse(str(body))


@app.get("/health")
def health():
    return {
        "ok": True,
        "doctor": ch.doctor(),
        "diagnose": ch.diagnose(),
        "otel": otel_status(),
        "trace": dashboard_snapshot(frame_limit=8),
    }


@app.get("/dx", response_class=HTMLResponse)
def dx():
    model = build_dashboard_model(doctor=ch.doctor(), latencies=[])
    return HTMLResponse(render_dashboard_html(model))


@app.get("/dx.json")
def dx_json():
    from ux_channel import serde as _serde
    from fastapi.responses import Response
    model = build_dashboard_model(doctor=ch.doctor(), latencies=[])
    return Response(_serde.dumps(model), media_type="application/json")
