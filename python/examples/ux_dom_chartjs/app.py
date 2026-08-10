"""
ux-dom + uxchannel + Chart.js — working stack example.

Layers
------
* **ux-dom** — document, layout, buttons (``ch.control(...).as_ux_dom()``)
* **uxchannel regions** — KPI strip + meta morph on action
* **ch.bridge** — host Placement + ``update`` / ``call`` ops
* **chartjs-adapter.js** — ``uxBridge.register("chart.js", …)`` loads Chart.js 4 (CDN)

Run::

    cd /workspace/uxchannel PYTHONPATH=src:/workspace/ux_dom-improve \\
      uvicorn examples.ux_dom_chartjs.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ux_channel import Channel, ChannelConfig, Region, Result
from ux_channel.demo import attr_string, mount_html, script_tags

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ux-dom + uxchannel · Chart.js")
app.mount("/demo-static", StaticFiles(directory=str(STATIC)), name="demo-static")

ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,  # local demo; keep True in production
    ),
)

# Contract: only these methods may be bridge.call'd
ch.bridge.register(
    "chart.js",
    methods=("update", "destroy", "setType"),
    description="Chart.js 4 via CDN adapter",
)

# ---------------------------------------------------------------------------
# Draft state + chart props
# ---------------------------------------------------------------------------

LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PALETTE = {
    "indigo": {
        "bg": "rgba(99, 102, 241, 0.65)",
        "border": "rgb(79, 70, 229)",
        "accent": "#4f46e5",
    },
    "emerald": {
        "bg": "rgba(16, 185, 129, 0.65)",
        "border": "rgb(5, 150, 105)",
        "accent": "#059669",
    },
    "rose": {
        "bg": "rgba(244, 63, 94, 0.65)",
        "border": "rgb(225, 29, 72)",
        "accent": "#e11d48",
    },
}


def _state() -> dict[str, Any]:
    s = ch.draft.get("dash")
    if not s:
        s = {
            "values": [12, 19, 8, 15, 22, 18, 25],
            "theme": "indigo",
            "chart_type": "bar",
            "title": "Weekly revenue",
        }
        ch.draft.set("dash", s)
    return s


def _chart_props() -> dict[str, Any]:
    s = _state()
    pal = PALETTE[s["theme"]]
    return {
        "type": s["chart_type"],
        "title": s["title"],
        "labels": LABELS,
        "datasets": [
            {
                "label": "Revenue ($k)",
                "data": list(s["values"]),
                "backgroundColor": pal["bg"],
                "borderColor": pal["border"],
                "borderWidth": 2,
                "borderRadius": 8,
                "tension": 0.35,
                "fill": s["chart_type"] == "line",
            }
        ],
    }


def _chart_ops() -> list:
    """Push new props into the live Chart.js instance (no remount)."""
    return ch.bridge.update_ops("rev-chart", _chart_props())


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------


class KpiStrip(Region):
    def render(self, ctx):
        s = _state()
        vals = s["values"]
        total = sum(vals)
        avg = total / max(len(vals), 1)
        peak = max(vals) if vals else 0
        pal = PALETTE[s["theme"]]["accent"]
        return f"""
        <div data-channel-id="{self.uid}" class="kpi-strip">
          <div class="kpi"><span class="kpi-label">Total</span>
            <span class="kpi-val" style="color:{pal}">${total}k</span></div>
          <div class="kpi"><span class="kpi-label">Average</span>
            <span class="kpi-val">${avg:.1f}k</span></div>
          <div class="kpi"><span class="kpi-label">Peak day</span>
            <span class="kpi-val">${peak}k</span></div>
          <div class="kpi"><span class="kpi-label">Theme</span>
            <span class="kpi-val" style="text-transform:capitalize">{s["theme"]}</span></div>
        </div>
        """


class ChartMeta(Region):
    def render(self, ctx):
        s = _state()
        return f"""
        <div data-channel-id="{self.uid}" class="chart-meta">
          <strong>{s["title"]}</strong>
          <span class="pill">{s["chart_type"]}</span>
          <span class="muted">Chart.js via ch.bridge</span>
        </div>
        """


kpi = ch.use(KpiStrip, uid="kpi.strip")
meta = ch.use(ChartMeta, uid="chart.meta")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@ch.on(name="Dash.randomize", refresh=[kpi, meta])
def randomize():
    s = _state()
    s["values"] = [random.randint(4, 32) for _ in LABELS]
    ch.draft.set("dash", s)
    r = ch.done(notice="Data reshuffled")
    return Result(ok=True, ops=list(r.ops) + _chart_ops(), meta=r.meta)


@ch.on(name="Dash.theme", refresh=[kpi, meta])
def cycle_theme():
    s = _state()
    keys = list(PALETTE.keys())
    s["theme"] = keys[(keys.index(s["theme"]) + 1) % len(keys)]
    ch.draft.set("dash", s)
    r = ch.done(notice=f"Theme → {s['theme']}")
    return Result(ok=True, ops=list(r.ops) + _chart_ops(), meta=r.meta)


@ch.on(name="Dash.type", refresh=[meta])
def cycle_type():
    s = _state()
    order = ["bar", "line", "doughnut"]
    s["chart_type"] = order[(order.index(s["chart_type"]) + 1) % len(order)]
    ch.draft.set("dash", s)
    r = ch.done(notice=f"Chart type → {s['chart_type']}")
    ops = list(r.ops) + _chart_ops()
    # string method on adapter (allowlisted)
    ops.extend(
        ch.bridge.call(
            "rev-chart",
            "setType",
            s["chart_type"],
            package="chart.js",
        )
    )
    return Result(ok=True, ops=ops, meta=r.meta)


@ch.on(name="Dash.nudge", refresh=[kpi, meta])
def nudge_friday():
    s = _state()
    vals = list(s["values"])
    vals[4] = min(40, vals[4] + random.randint(1, 5))
    s["values"] = vals
    ch.draft.set("dash", s)
    r = ch.done(notice="Friday nudged")
    return Result(ok=True, ops=list(r.ops) + _chart_ops(), meta=r.meta)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #0b1020; --panel: #121a2f; --ink: #e8eefc; --muted: #93a0c0;
  --line: rgba(255,255,255,.08); --accent: #818cf8; --radius: 16px;
  font-family: "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; color: var(--ink);
  background:
    radial-gradient(1200px 600px at 10% -10%, #1e1b4b 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #064e3b 0%, transparent 50%),
    var(--bg);
}
.wrap { max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
header h1 { margin: 0 0 .35rem; font-size: 1.75rem; letter-spacing: -.02em; }
header p { margin: 0; color: var(--muted); line-height: 1.5; max-width: 40rem; }
.panel {
  background: linear-gradient(180deg, rgba(255,255,255,.04), transparent 40%), var(--panel);
  border: 1px solid var(--line); border-radius: var(--radius); padding: 1.25rem;
  box-shadow: 0 20px 50px rgba(0,0,0,.35);
}
.kpi-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; margin-bottom: 1rem; }
@media (max-width: 720px) { .kpi-strip { grid-template-columns: repeat(2, 1fr); } }
.kpi {
  background: rgba(0,0,0,.22); border: 1px solid var(--line); border-radius: 12px;
  padding: .85rem 1rem; display: flex; flex-direction: column; gap: .25rem;
}
.kpi-label { font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.kpi-val { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.chart-meta { display: flex; align-items: center; gap: .65rem; flex-wrap: wrap; margin-bottom: .75rem; }
.pill {
  font-size: .7rem; text-transform: uppercase; letter-spacing: .05em;
  padding: .2rem .5rem; border-radius: 999px;
  background: rgba(129,140,248,.18); color: #c7d2fe; border: 1px solid rgba(129,140,248,.35);
}
.muted { color: var(--muted); font-size: .85rem; }
.chart-host {
  height: 320px; position: relative; background: rgba(0,0,0,.18);
  border-radius: 12px; padding: .75rem; border: 1px solid var(--line);
}
.toolbar { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
button.action {
  appearance: none; cursor: pointer; border: 1px solid var(--line);
  background: rgba(255,255,255,.06); color: var(--ink);
  border-radius: 999px; padding: .55rem 1rem; font-weight: 600; font-size: .9rem;
}
button.action:hover { background: rgba(129,140,248,.2); border-color: rgba(129,140,248,.45); }
button.action.primary {
  background: linear-gradient(135deg, #6366f1, #4f46e5); border-color: transparent;
}
.foot { margin-top: 1.5rem; color: var(--muted); font-size: .8rem; }
.foot code { color: #c7d2fe; }
.tag { display: inline-flex; gap: .35rem; margin-bottom: .75rem; font-size: .75rem; color: var(--muted); }
.tag span {
  background: rgba(255,255,255,.06); border: 1px solid var(--line);
  border-radius: 6px; padding: .15rem .45rem;
}
"""


def _btn(label: str, action, *, primary: bool = False):
    from ux_dom.dom import button

    cls = "action primary" if primary else "action"
    return button(
        label,
        type="button",
        className=cls,
        **ch.control(action).as_ux_dom(),
    )


def _head_scripts() -> str:
    """Placement → script tags (demo helper). Adapter after channel scripts."""
    return (
        script_tags(ch.runtime())
        + '\n<script src="/demo-static/chartjs-adapter.js" defer></script>\n'
        + """
<script>
document.addEventListener('DOMContentLoaded', function () {
  function mountChart() {
    if (!window.uxBridge) return setTimeout(mountChart, 30);
    var host = document.querySelector('[data-channel-bridge-id="rev-chart"]');
    if (!host) return;
    var raw = host.getAttribute('data-channel-bridge-props');
    var props = {};
    try { props = raw ? JSON.parse(raw) : {}; } catch (e) {}
    uxBridge.apply({
      op: 'bridge.mount',
      id: 'rev-chart',
      package: 'chart.js',
      props: props,
      target: '[data-channel-bridge-id="rev-chart"]'
    });
  }
  mountChart();
});
</script>
"""
    )


def _chart_host() -> str:
    # Placement from ch.bridge → demo HTML host only at the edge
    spec = ch.bridge.mount_spec(
        "rev-chart",
        package="chart.js",
        props=_chart_props(),
    )
    return mount_html(
        spec,
        class_name="chart-host",
        tag="div",
        inner='<canvas aria-label="Revenue chart"></canvas>',
    )


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        from ux_dom import Document
        from ux_dom.dom import div, h1, p, raw, span

        head = [
            raw(f"<style>{CSS}</style>"),
            raw(_head_scripts()),
        ]
        doc = Document(head=head)
        body = div(
            div(
                div(
                    span("ux-dom"),
                    span("ux-channel"),
                    span("Chart.js"),
                    className="tag",
                ),
                h1("Live revenue console"),
                p(
                    "Regions morph KPIs; the chart is a real Chart.js instance "
                    "driven by ch.bridge.update / ch.bridge.call — no React, no reload."
                ),
            ),
            div(
                raw(kpi()),
                raw(meta()),
                raw(_chart_host()),
                div(
                    _btn("Reshuffle data", randomize, primary=True),
                    _btn("Nudge Friday", nudge_friday),
                    _btn("Cycle theme", cycle_theme),
                    _btn("Bar → Line → Doughnut", cycle_type),
                    className="toolbar",
                ),
                className="panel",
            ),
            p(
                raw(
                    "Adapter <code>/demo-static/chartjs-adapter.js</code> · "
                    "CDN chart.js@4 · Placement via <code>ch.bridge.mount_spec</code>"
                ),
                className="foot",
            ),
            className="wrap",
        )
        html = str(doc(body))
        body_attrs = attr_string(ch.runtime().attrs) if hasattr(ch.runtime(), "attrs") else ""
        # prefer channel body endpoint attrs
        try:
            body_attrs = attr_string(ch.body_attrs())
        except Exception:
            pass
        if "<body" in html:
            html = html.replace("<body", f"<body {body_attrs}", 1)
        return HTMLResponse(html)
    except ImportError:
        # HTML-only fallback (no ux-dom)
        def ba(action):
            return attr_string(ch.control(action).as_dict())

        try:
            body_attrs = attr_string(ch.body_attrs())
        except Exception:
            body_attrs = ""
        return HTMLResponse(
            f"""<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>{CSS}</style>
{_head_scripts()}
</head>
<body {body_attrs}>
<div class="wrap">
  <header>
    <div class="tag"><span>HTML</span><span>ux-channel</span><span>Chart.js</span></div>
    <h1>Live revenue console</h1>
    <p>Chart.js via bridge + regions for KPIs (install ux_dom for ux-dom markup).</p>
  </header>
  <div class="panel">
    {kpi()}
    {meta()}
    {_chart_host()}
    <div class="toolbar">
      <button type="button" class="action primary" {ba(randomize)}>Reshuffle data</button>
      <button type="button" class="action" {ba(nudge_friday)}>Nudge Friday</button>
      <button type="button" class="action" {ba(cycle_theme)}>Cycle theme</button>
      <button type="button" class="action" {ba(cycle_type)}>Bar → Line → Doughnut</button>
    </div>
  </div>
</div>
</body></html>"""
        )


@app.get("/health")
def health():
    return {
        "ok": True,
        "chart_package": "chart.js",
        "bridge": ch.bridge.packages(),
        "stack": ["ux_dom", "ux-channel", "chart.js"],
    }
