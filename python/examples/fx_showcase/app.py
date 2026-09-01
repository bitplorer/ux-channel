"""
First-party builtin islands — confetti, particles, aurora, count-up, spotlight.

Run: uvicorn examples.fx_showcase.app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import (
    AuroraBridge,
    ConfettiBridge,
    CountUpBridge,
    ParticlesBridge,
    SpotlightBridge,
)
from ux_channel.render.kit import attr_string, builtins_script_tags, demo_button, script_tags

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-fx-showcase-secret-key-32b!",
        allow_memory_stores=True,
        require_cap=False,
    ),
)

aurora = AuroraBridge(ch)("hero-bg", theme="candy", intensity=0.9)
particles = ParticlesBridge(ch)("hero-particles", theme="aurora", count=48)
confetti = ConfettiBridge(ch)("celebrate", theme="neon")
mrr = CountUpBridge(ch)("mrr", value=12840, prefix="$", theme="emerald")
spot = SpotlightBridge(ch)("feature-card", theme="violet")


@ch.on
def celebrate():
    return confetti.burst()


@ch.on
def bump_mrr():
    n = float(ch.draft.get("mrr", 12840) or 12840) + 420
    ch.draft.set("mrr", n)
    return mrr.commit(value=n, notice="MRR up")


@ch.on
def pulse_field():
    return particles.pulse()


@app.get("/", response_class=HTMLResponse)
def index():
    rt = ch.runtime()
    body = ch.body_attrs()
    ab = aurora.mount_spec(class_name="fx-layer", style="position:fixed;inset:0;z-index:0")
    pb = particles.mount_spec(
        class_name="fx-layer", style="position:fixed;inset:0;z-index:1;pointer-events:none"
    )
    cb = confetti.mount_spec(
        style="position:fixed;inset:0;z-index:50;pointer-events:none"
    )
    mb = mrr.mount_spec(style="font-size:3rem;line-height:1")
    sb = spot.mount_spec(
        class_name="card",
        style="position:relative;padding:2rem;border-radius:1.25rem;"
        "background:rgba(15,23,42,.72);border:1px solid rgba(148,163,184,.2);"
        "backdrop-filter:blur(12px);max-width:28rem",
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>builtin islands showcase</title>
  {script_tags(rt)}
  {builtins_script_tags(bridge=True)}
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif;
      background:#020617; color:#e2e8f0; min-height:100vh; }}
    .wrap {{ position:relative; z-index:10; max-width:56rem; margin:0 auto;
      padding:4rem 1.5rem 6rem; }}
    h1 {{ font-size:clamp(2rem,5vw,3.25rem); letter-spacing:-.03em; margin:0 0 .5rem; }}
    p.lead {{ color:#94a3b8; max-width:36rem; line-height:1.6; }}
    .row {{ display:flex; flex-wrap:wrap; gap:1rem; margin-top:2rem; align-items:center; }}
    button {{ cursor:pointer; border:0; border-radius:.75rem; padding:.75rem 1.1rem;
      font-weight:600; background:linear-gradient(135deg,#8b5cf6,#06b6d4); color:white; }}
    button.secondary {{ background:rgba(30,41,59,.9); border:1px solid rgba(148,163,184,.25); }}
    .grid {{ display:grid; gap:1.25rem; margin-top:2.5rem;
      grid-template-columns:repeat(auto-fit,minmax(16rem,1fr)); }}
    .muted {{ color:#94a3b8; font-size:.9rem; }}
  </style>
</head>
<body {attr_string(body)}>
  <div {attr_string(ab)}></div>
  <div {attr_string(pb)}></div>
  <div {attr_string(cb)}></div>
  <div class="wrap">
    <h1>builtin islands</h1>
    <p class="lead">First-party packs as data + ops — confetti, particles, aurora,
    count-up, spotlight. Host styles stay in your markup; packages stay dumb.</p>
    <div class="row">
      {demo_button(ch, "Celebrate", celebrate)}
      {demo_button(ch, "Bump MRR", bump_mrr)}
      {demo_button(ch, "Pulse field", pulse_field)}
    </div>
    <div class="grid">
      <div {attr_string(sb)}>
        <div class="muted">Monthly revenue</div>
        <div {attr_string(mb)}></div>
        <p class="muted" style="margin-top:1rem">Spotlight follows the pointer on this card.</p>
      </div>
    </div>
  </div>
  <script>
    document.addEventListener("DOMContentLoaded", function () {{
      if (window.uxBridge && window.uxBridge.scan) window.uxBridge.scan();
    }});
  </script>
</body>
</html>"""
