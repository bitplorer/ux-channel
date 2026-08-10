from ux_channel.bridge.bridge_api import mount_html, mount_ops, update_ops, register_simple_manifest
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
"""
ux-dom + uxchannel + three.js (npm 3D via CDN bridge)

Regions morph the HUD; the WebGL canvas is a real three.js scene
driven by bridge.update / bridge.call.

Run:
  PYTHONPATH=src:/tmp/ux_dom uvicorn examples.ux_dom_threejs.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ux_channel import (
    Channel,
    ChannelConfig,
    Region,
    Result,
    register_simple_manifest,
    update_ops,
)
from ux_channel.protocol.ops import bridge_call

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ux_dom + uxchannel · three.js")
app.mount("/demo-static", StaticFiles(directory=str(STATIC)), name="demo-static")

ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
    ),
)

register_simple_manifest(
    "three",
    methods=("update", "destroy", "setShape", "setColor", "toggleWireframe", "toggleSpin", "pulse"),
    description="three.js r160 WebGL scene via CDN",
    hub=getattr(ch, "hub", None),
)

SHAPES = ["torus", "box", "icosahedron", "sphere"]
COLORS = [
    ("indigo", "#6366f1"),
    ("emerald", "#10b981"),
    ("rose", "#f43f5e"),
    ("amber", "#f59e0b"),
    ("sky", "#0ea5e9"),
]


def _state() -> dict[str, Any]:
    s = ch.draft.get("scene3d")
    if not s:
        s = {
            "shape": "torus",
            "color": "#6366f1",
            "color_name": "indigo",
            "wireframe": False,
            "autoRotate": True,
            "speed": 1.0,
            "metalness": 0.45,
            "roughness": 0.3,
            "bg": "#0b1020",
            "spins": 0,
            "pulses": 0,
        }
        ch.draft.set("scene3d", s)
    return s


def _props() -> dict[str, Any]:
    s = _state()
    return {
        "shape": s["shape"],
        "color": s["color"],
        "wireframe": s["wireframe"],
        "autoRotate": s["autoRotate"],
        "speed": s["speed"],
        "metalness": s["metalness"],
        "roughness": s["roughness"],
        "bg": s["bg"],
    }


def _bridge_update() -> list:
    return update_ops("scene-3d", _props())


class Hud(Region):
    def render(self, ctx):
        s = _state()
        spin = "on" if s["autoRotate"] else "off"
        wire = "on" if s["wireframe"] else "off"
        return f"""
        <div data-channel-id="{self.uid}" class="hud">
          <div class="stat"><span class="lbl">Shape</span><span class="val">{s["shape"]}</span></div>
          <div class="stat"><span class="lbl">Color</span>
            <span class="val swatch" style="--c:{s["color"]}">{s["color_name"]}</span></div>
          <div class="stat"><span class="lbl">Spin</span><span class="val">{spin}</span></div>
          <div class="stat"><span class="lbl">Wire</span><span class="val">{wire}</span></div>
          <div class="stat"><span class="lbl">Speed</span><span class="val">{s["speed"]:.1f}×</span></div>
          <div class="stat"><span class="lbl">Pulses</span><span class="val">{s["pulses"]}</span></div>
        </div>
        """


class Caption(Region):
    def render(self, ctx):
        s = _state()
        return f"""
        <div data-channel-id="{self.uid}" class="caption">
          <strong>three.js</strong> · {s["shape"]} · drag to orbit ·
          <span class="muted">npm package via ux-bridge CDN load</span>
        </div>
        """


hud = ch.use(Hud, uid="hud.panel")
caption = ch.use(Caption, uid="scene.caption")


@ch.on(name="Scene3d.nextShape", refresh=[hud, caption])
def next_shape():
    s = _state()
    s["shape"] = SHAPES[(SHAPES.index(s["shape"]) + 1) % len(SHAPES)]
    ch.draft.set("scene3d", s)
    r = ch.done(notice=f"Shape → {s['shape']}")
    ops = list(r.ops) + _bridge_update()
    ops.append(bridge_call("scene-3d", "setShape", [s["shape"]]))
    return Result(ok=True, ops=ops, meta=r.meta)


@ch.on(name="Scene3d.nextColor", refresh=[hud])
def next_color():
    s = _state()
    names = [c[0] for c in COLORS]
    i = names.index(s["color_name"]) if s["color_name"] in names else 0
    name, hex_ = COLORS[(i + 1) % len(COLORS)]
    s["color_name"], s["color"] = name, hex_
    ch.draft.set("scene3d", s)
    r = ch.done(notice=f"Color → {name}")
    ops = list(r.ops) + _bridge_update()
    ops.append(bridge_call("scene-3d", "setColor", [hex_]))
    return Result(ok=True, ops=ops, meta=r.meta)


@ch.on(name="Scene3d.toggleWire", refresh=[hud])
def toggle_wire():
    s = _state()
    s["wireframe"] = not s["wireframe"]
    ch.draft.set("scene3d", s)
    r = ch.done(notice="Wireframe toggled")
    ops = list(r.ops) + _bridge_update()
    ops.append(bridge_call("scene-3d", "toggleWireframe", []))
    return Result(ok=True, ops=ops, meta=r.meta)


@ch.on(name="Scene3d.toggleSpin", refresh=[hud])
def toggle_spin():
    s = _state()
    s["autoRotate"] = not s["autoRotate"]
    s["spins"] = int(s.get("spins", 0)) + 1
    ch.draft.set("scene3d", s)
    r = ch.done(notice="Spin " + ("on" if s["autoRotate"] else "off"))
    ops = list(r.ops) + _bridge_update()
    ops.append(bridge_call("scene-3d", "toggleSpin", []))
    return Result(ok=True, ops=ops, meta=r.meta)


@ch.on(name="Scene3d.faster", refresh=[hud])
def faster():
    s = _state()
    s["speed"] = min(3.0, round(float(s["speed"]) + 0.25, 2))
    ch.draft.set("scene3d", s)
    r = ch.done(notice=f"Speed {s['speed']}×")
    return Result(ok=True, ops=list(r.ops) + _bridge_update(), meta=r.meta)


@ch.on(name="Scene3d.slower", refresh=[hud])
def slower():
    s = _state()
    s["speed"] = max(0.25, round(float(s["speed"]) - 0.25, 2))
    ch.draft.set("scene3d", s)
    r = ch.done(notice=f"Speed {s['speed']}×")
    return Result(ok=True, ops=list(r.ops) + _bridge_update(), meta=r.meta)


@ch.on(name="Scene3d.pulse", refresh=[hud])
def pulse():
    s = _state()
    s["pulses"] = int(s.get("pulses", 0)) + 1
    ch.draft.set("scene3d", s)
    r = ch.done(notice="Pulse")
    ops = list(r.ops) + [bridge_call("scene-3d", "pulse", [])]
    return Result(ok=True, ops=ops, meta=r.meta)


CSS = """
:root {
  --bg: #070b16;
  --panel: #0f172a;
  --ink: #e2e8f0;
  --muted: #94a3b8;
  --line: rgba(148,163,184,.16);
  --accent: #818cf8;
  font-family: "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; color: var(--ink);
  background:
    radial-gradient(900px 500px at 80% -10%, #312e81 0%, transparent 55%),
    radial-gradient(700px 400px at 0% 100%, #134e4a 0%, transparent 50%),
    var(--bg);
}
.wrap { max-width: 980px; margin: 0 auto; padding: 1.75rem 1.2rem 3rem; }
header h1 { margin: 0 0 .4rem; font-size: 1.7rem; letter-spacing: -.02em; }
header p { margin: 0; color: var(--muted); max-width: 36rem; line-height: 1.5; }
.tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .85rem; }
.tags span {
  font-size: .72rem; padding: .18rem .5rem; border-radius: 6px;
  border: 1px solid var(--line); background: rgba(255,255,255,.04); color: var(--muted);
}
.stage {
  margin-top: 1.25rem;
  background: linear-gradient(180deg, rgba(255,255,255,.03), transparent 50%), var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1rem;
  box-shadow: 0 24px 60px rgba(0,0,0,.4);
}
.hud {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: .5rem;
  margin-bottom: .85rem;
}
@media (max-width: 800px) {
  .hud { grid-template-columns: repeat(3, 1fr); }
}
.stat {
  background: rgba(0,0,0,.28);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: .65rem .75rem;
  display: flex; flex-direction: column; gap: .2rem;
}
.lbl { font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.val { font-weight: 700; font-size: .98rem; text-transform: capitalize; }
.swatch::before {
  content: ""; display: inline-block; width: .7rem; height: .7rem;
  border-radius: 999px; background: var(--c); margin-right: .4rem;
  vertical-align: -1px; box-shadow: 0 0 0 2px rgba(255,255,255,.08);
}
.caption { margin-bottom: .65rem; font-size: .92rem; }
.muted { color: var(--muted); font-size: .85rem; }
.viewport {
  height: min(52vh, 420px);
  min-height: 280px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: #020617;
  overflow: hidden;
  touch-action: none;
  cursor: grab;
}
.viewport:active { cursor: grabbing; }
.toolbar {
  display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem;
}
button.action {
  appearance: none; cursor: pointer;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.05);
  color: var(--ink);
  border-radius: 999px;
  padding: .55rem 1rem;
  font-weight: 600; font-size: .88rem;
}
button.action:hover { border-color: rgba(129,140,248,.5); background: rgba(129,140,248,.15); }
button.action.primary {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border-color: transparent;
}
.foot { margin-top: 1.25rem; color: var(--muted); font-size: .8rem; }
.foot code { color: #c7d2fe; }
"""


def _host() -> str:
    return mount_html(
        "scene-3d",
        package="three",
        props=_props(),
        class_name="viewport",
        tag="div",
        inner="",
    )


def _btn_html(label: str, action, *, primary: bool = False) -> str:
    d = ch.control(action).as_dict()
    attrs = " ".join(f'{k}="{v}"' for k, v in d.items())
    cls = "action primary" if primary else "action"
    return f'<button type="button" class="{cls}" {attrs}>{label}</button>'


@app.get("/", response_class=HTMLResponse)
def index():
    scripts = str(demo_scripts(ch, ))
    extra = (
        '<script src="/demo-static/threejs-adapter.js" defer></script>'
        """
<script>
document.addEventListener('DOMContentLoaded', function () {
  function mountScene() {
    if (!window.uxBridge) return setTimeout(mountScene, 40);
    var host = document.querySelector('[data-channel-bridge-id="scene-3d"]');
    if (!host) return;
    var raw = host.getAttribute('data-channel-bridge-props');
    var props = {};
    try { props = raw ? JSON.parse(raw) : {}; } catch (e) {}
    uxBridge.apply({
      op: 'bridge.mount',
      id: 'scene-3d',
      package: 'three',
      props: props,
      target: '[data-channel-bridge-id="scene-3d"]'
    });
  }
  mountScene();
});
</script>
"""
    )

    try:
        from ux_dom import Document
        from ux_dom.dom import button, div, h1, p, raw, span

        def btn(label, action, primary=False):
            cls = "action primary" if primary else "action"
            return button(
                label,
                type="button",
                className=cls,
                **ch.control(action).as_ux_dom(),
            )

        doc = Document(
            head=[
                raw('<meta name="viewport" content="width=device-width,initial-scale=1">'),
                raw(f"<style>{CSS}</style>"),
                raw(scripts),
                raw(extra),
            ]
        )
        page = div(
            div(
                div(
                    span("ux-dom"),
                    span("ux-channel"),
                    span("three.js npm"),
                    className="tags",
                ),
                h1("3D scene console"),
                p(
                    "A real WebGL scene from the three.js npm package, "
                    "mounted through ux-bridge. Channel actions call into the "
                    "mesh (shape, color, spin, pulse) while regions morph the HUD."
                ),
            ),
            div(
                raw(hud()),
                raw(caption()),
                raw(_host()),
                div(
                    btn("Next shape", next_shape, True),
                    btn("Next color", next_color),
                    btn("Wireframe", toggle_wire),
                    btn("Toggle spin", toggle_spin),
                    btn("Faster", faster),
                    btn("Slower", slower),
                    btn("Pulse", pulse),
                    className="toolbar",
                ),
                className="stage",
            ),
            p(
                raw(
                    "Adapter <code>/demo-static/threejs-adapter.js</code> · "
                    "CDN three@0.160 · drag canvas to orbit"
                ),
                className="foot",
            ),
            className="wrap",
        )
        html = str(doc(page))
        if "<body" in html:
            html = html.replace("<body", f"<body {attr_string(ch.body_attrs())}", 1)
        else:
            html = (
                f"<!doctype html><html><head></head>"
                f"<body {attr_string(ch.body_attrs())}>{html}</body></html>"
            )
        return HTMLResponse(html)
    except ImportError:
        return HTMLResponse(
            f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style>{scripts}{extra}</head>
<body {attr_string(ch.body_attrs())}>
<div class="wrap">
  <header>
    <div class="tags"><span>HTML</span><span>ux-channel</span><span>three.js</span></div>
    <h1>3D scene console</h1>
    <p>three.js via bridge plane + channel HUD regions.</p>
  </header>
  <div class="stage">
    {hud()}{caption()}{_host()}
    <div class="toolbar">
      {_btn_html("Next shape", next_shape, primary=True)}
      {_btn_html("Next color", next_color)}
      {_btn_html("Wireframe", toggle_wire)}
      {_btn_html("Toggle spin", toggle_spin)}
      {_btn_html("Faster", faster)}
      {_btn_html("Slower", slower)}
      {_btn_html("Pulse", pulse)}
    </div>
  </div>
</div>
</body></html>"""
        )


@app.get("/health")
def health():
    return {"ok": True, "package": "three", "ux_channel": "0.1.0"}
