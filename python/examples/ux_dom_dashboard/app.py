"""
Analytics dashboard — ux-dom (document/widgets) + uxchannel (regions/actions).

  PYTHONPATH=src:/tmp/ux_dom uvicorn examples.ux_dom_dashboard.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import math
import random
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_dom import Document
from ux_dom.dom import button, div, h1, h2, p, raw, span

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

# ---------------------------------------------------------------------------
# App + channel
# ---------------------------------------------------------------------------

app = FastAPI(title="ux_dom-dashboard")
SECRET = "dashboard-secret-key-32chars-min!!!!"
ch = Channel.boot(
    app,
    config=ChannelConfig.development(secret=SECRET, allow_memory_stores=True),
)

# ---------------------------------------------------------------------------
# In-memory analytics (demo "DB")
# ---------------------------------------------------------------------------

PERIODS = ("7d", "30d", "90d")
PERIOD_LABELS = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}

SERIES = {
    "7d": {
        "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "revenue": [12.4, 15.1, 13.8, 18.2, 21.0, 16.5, 19.4],
        "visitors": [820, 940, 880, 1100, 1320, 980, 1200],
        "mix": {"Organic": 42, "Paid": 28, "Referral": 18, "Direct": 12},
    },
    "30d": {
        "labels": [f"W{i}" for i in range(1, 5)],
        "revenue": [48, 52, 61, 58],
        "visitors": [4200, 4800, 5100, 4950],
        "mix": {"Organic": 38, "Paid": 32, "Referral": 16, "Direct": 14},
    },
    "90d": {
        "labels": ["Jan", "Feb", "Mar"],
        "revenue": [142, 168, 191],
        "visitors": [14200, 15800, 17100],
        "mix": {"Organic": 35, "Paid": 35, "Referral": 15, "Direct": 15},
    },
}


def _period() -> str:
    p = ch.draft.get("period") or "7d"
    return p if p in SERIES else "7d"


def _data() -> dict[str, Any]:
    return SERIES[_period()]


def _kpis() -> dict[str, Any]:
    d = _data()
    rev = d["revenue"]
    vis = d["visitors"]
    total_rev = sum(rev)
    total_vis = sum(vis)
    prev = total_rev * 0.88
    growth = ((total_rev - prev) / prev) * 100 if prev else 0
    aov = (total_rev * 1000) / max(total_vis, 1)
    return {
        "revenue": total_rev,
        "visitors": total_vis,
        "growth": growth,
        "aov": aov,
        "orders": int(total_vis * 0.034),
    }


# ---------------------------------------------------------------------------
# SVG chart primitives (SSR-friendly, morph cleanly)
# ---------------------------------------------------------------------------

PALETTE = ["#14b8a6", "#38bdf8", "#a78bfa", "#f472b6", "#fbbf24"]
INK = "#e7e7ea"
MUTED = "#8b8b9a"
GRID = "#26262f"
SURFACE = "#12121a"


def _esc(s: Any) -> str:
    t = str(s)
    t = t.replace('&', '&amp;')
    t = t.replace('<', '&lt;')
    t = t.replace('>', '&gt;')
    t = t.replace(chr(34), '&quot;')
    return t

def svg_bar_chart(
    labels: list[str],
    values: list[float],
    *,
    width: int = 560,
    height: int = 220,
    color: str = PALETTE[0],
    unit: str = "k",
) -> str:
    pad_l, pad_r, pad_t, pad_b = 36, 12, 16, 32
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max(values) * 1.15 or 1
    n = len(values)
    gap = 0.28
    bw = plot_w / max(n, 1)
    bar_w = bw * (1 - gap)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Bar chart" class="chart-svg">'
    ]
    # grid
    for i in range(5):
        y = pad_t + plot_h * i / 4
        val = vmax * (1 - i / 4)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="{MUTED}" font-size="10" font-family="system-ui">{val:.0f}{unit}</text>'
        )
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = pad_l + i * bw + bw * gap / 2
        h = (v / vmax) * plot_h
        y = pad_t + plot_h - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'rx="4" fill="{color}" opacity="0.92">'
            f"<title>{_esc(lab)}: {v}{unit}</title></rect>"
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 10}" text-anchor="middle" '
            f'fill="{MUTED}" font-size="11" font-family="system-ui">{_esc(lab)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_line_chart(
    labels: list[str],
    values: list[float],
    *,
    width: int = 560,
    height: int = 220,
    color: str = PALETTE[1],
) -> str:
    pad_l, pad_r, pad_t, pad_b = 40, 12, 16, 32
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max(values) * 1.12 or 1
    n = max(len(values) - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = pad_l + (i / n) * plot_w
        y = pad_t + plot_h - (v / vmax) * plot_h
        pts.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad_l},{pad_t + plot_h} " + line + f" {pts[-1][0]:.1f},{pad_t + plot_h}"
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Line chart" class="chart-svg">'
        f'<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
    ]
    for i in range(5):
        y = pad_t + plot_h * i / 4
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
    parts.append(f'<polygon points="{area}" fill="url(#areaFill)"/>')
    parts.append(
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for (x, y), lab, v in zip(pts, labels, values):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{SURFACE}" '
            f'stroke="{color}" stroke-width="2"><title>{_esc(lab)}: {v}</title></circle>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" '
            f'fill="{MUTED}" font-size="11" font-family="system-ui">{_esc(lab)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_donut(
    mix: dict[str, float],
    *,
    size: int = 200,
    thickness: float = 28,
) -> str:
    total = sum(mix.values()) or 1
    cx = cy = size / 2
    r = size / 2 - 8
    r_inner = r - thickness
    # Use stroke-dash ring segments
    circ = 2 * math.pi * ((r + r_inner) / 2)
    parts = [
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'role="img" aria-label="Traffic mix" class="chart-svg donut">'
    ]
    # background ring
    mid_r = (r + r_inner) / 2
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{mid_r}" fill="none" '
        f'stroke="{GRID}" stroke-width="{thickness}"/>'
    )
    offset = 0.0
    for i, (name, val) in enumerate(mix.items()):
        frac = val / total
        dash = frac * circ
        gap = circ - dash
        color = PALETTE[i % len(PALETTE)]
        # start from top
        rot = -90 + (offset / circ) * 360
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{mid_r}" fill="none" '
            f'stroke="{color}" stroke-width="{thickness}" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="0" '
            f'transform="rotate({rot:.2f} {cx} {cy})" '
            f'stroke-linecap="butt">'
            f"<title>{_esc(name)}: {val}%</title></circle>"
        )
        offset += dash
    parts.append(
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" fill="{INK}" '
        f'font-size="22" font-weight="600" font-family="system-ui">100%</text>'
        f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" fill="{MUTED}" '
        f'font-size="11" font-family="system-ui">mix</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# CSS (single coherent system — no purple slop)
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #0b0b0f;
  --surface: #12121a;
  --surface-2: #1a1a24;
  --fg: #e7e7ea;
  --muted: #8b8b9a;
  --primary: #14b8a6;
  --primary-dim: rgba(20, 184, 166, 0.15);
  --border: #26262f;
  --up: #34d399;
  --down: #f87171;
  --radius: 12px;
  --font: "DM Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; min-height: 100%;
  background: var(--bg); color: var(--fg);
  font-family: var(--font); line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
button:not(:disabled), [role="button"]:not(:disabled) { cursor: pointer; }
a { color: var(--primary); }
.shell {
  max-width: 1120px; margin: 0 auto;
  padding: 1.25rem 1rem 3rem;
}
.top {
  display: flex; flex-wrap: wrap; align-items: flex-end;
  justify-content: space-between; gap: 1rem;
  margin-bottom: 1.5rem;
}
.brand {
  font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--muted); margin: 0 0 0.25rem;
}
h1 {
  margin: 0; font-size: clamp(1.5rem, 3vw, 1.85rem); font-weight: 650;
  letter-spacing: -0.02em;
}
.sub { margin: 0.35rem 0 0; color: var(--muted); font-size: 0.95rem; }
.period {
  display: inline-flex; gap: 0.35rem; padding: 0.25rem;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px;
}
.period button {
  border: 0; background: transparent; color: var(--muted);
  font: inherit; font-size: 0.85rem; font-weight: 500;
  padding: 0.45rem 0.9rem; border-radius: 999px;
  min-height: 40px; transition: background .15s, color .15s;
}
.period button[aria-pressed="true"] {
  background: var(--primary-dim); color: var(--primary);
}
.period button:hover { color: var(--fg); }
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem; margin-bottom: 1rem;
}
.kpi {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem 1.1rem;
}
.kpi .label {
  font-size: 0.75rem; color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.06em; margin: 0 0 0.35rem;
}
.kpi .value {
  font-size: 1.45rem; font-weight: 650; letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; margin: 0;
}
.kpi .delta {
  font-size: 0.8rem; margin: 0.35rem 0 0; font-variant-numeric: tabular-nums;
}
.delta.up { color: var(--up); }
.delta.down { color: var(--down); }
.grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0.85rem;
}
@media (max-width: 840px) {
  .grid { grid-template-columns: 1fr; }
}
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem 1.1rem 0.75rem;
  min-width: 0;
}
.card h2 {
  margin: 0 0 0.15rem; font-size: 0.95rem; font-weight: 600;
}
.card .hint { margin: 0 0 0.75rem; font-size: 0.8rem; color: var(--muted); }
.legend {
  list-style: none; margin: 0.75rem 0 0; padding: 0;
  display: flex; flex-direction: column; gap: 0.4rem;
}
.legend li {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.85rem; gap: 0.75rem;
}
.swatch {
  width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0;
}
.legend .name { display: flex; align-items: center; gap: 0.5rem; color: var(--muted); }
.legend .pct { font-variant-numeric: tabular-nums; font-weight: 600; }
.actions {
  display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem;
}
.btn {
  border: 1px solid var(--border); background: var(--surface-2);
  color: var(--fg); font: inherit; font-size: 0.875rem; font-weight: 500;
  padding: 0.55rem 1rem; border-radius: 8px; min-height: 44px;
  transition: border-color .15s, background .15s;
}
.btn:hover { border-color: var(--primary); }
.btn-primary {
  background: var(--primary); border-color: var(--primary); color: #042f2e;
  font-weight: 600;
}
.btn-primary:hover { filter: brightness(1.05); }
.flash {
  margin: 0 0 1rem; padding: 0.65rem 0.9rem; border-radius: 8px;
  background: var(--primary-dim); color: var(--primary);
  font-size: 0.9rem; border: 1px solid rgba(20,184,166,0.25);
  min-height: 1.2em;
}
.flash:empty { display: none; }
.footer {
  margin-top: 2rem; color: var(--muted); font-size: 0.8rem;
}
.chart-svg { display: block; max-width: 100%; }
.donut-wrap {
  display: flex; flex-wrap: wrap; align-items: center; gap: 1.25rem;
}
"""

document = Document(
    head=[
        raw(
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"/>'
            '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>'
            f"<style>{CSS}</style>"
        ),
        raw(str(demo_scripts(ch, ))),
    ]
)


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------


class FlashBar(Region):
    def render(self, ctx):
        msg = ch.draft.get("flash") or ""
        return div(msg, className="flash")


class PeriodPicker(Region):
    def render(self, ctx):
        cur = _period()
        btns = []
        for key in PERIODS:
            btns.append(
                button(
                    PERIOD_LABELS[key],
                    type="button",
                    **{"aria-pressed": "true" if key == cur else "false"},
                    **ch.control(self.set_period, trust_period=key).as_ux_dom(),
                )
            )
        return div(*btns, className="period")

    @Region.action(refresh=["flash.bar", "kpi.row", "chart.revenue", "chart.traffic", "chart.mix"])
    def set_period(self, period: str = "7d"):
        if period not in SERIES:
            period = "7d"
        ch.draft.set("period", period)
        ch.draft.set("flash", f"Showing {PERIOD_LABELS[period]}")
        return None


class KpiRow(Region):
    def render(self, ctx):
        k = _kpis()
        growth = k["growth"]
        cls = "up" if growth >= 0 else "down"
        sign = "+" if growth >= 0 else ""
        cards = [
            div(
                p("Revenue", className="label"),
                p(f"${k['revenue']:.1f}k", className="value"),
                p(f"{sign}{growth:.1f}% vs prior", className=f"delta {cls}"),
                className="kpi",
            ),
            div(
                p("Visitors", className="label"),
                p(f"{k['visitors']:,}", className="value"),
                p(f"Period · {_period()}", className="delta"),
                className="kpi",
            ),
            div(
                p("Orders", className="label"),
                p(f"{k['orders']:,}", className="value"),
                p("≈ 3.4% conversion", className="delta"),
                className="kpi",
            ),
            div(
                p("AOV", className="label"),
                p(f"${k['aov']:.2f}", className="value"),
                p("Per visitor proxy", className="delta"),
                className="kpi",
            ),
        ]
        return div(*cards, className="kpis")


class RevenueChart(Region):
    def render(self, ctx):
        d = _data()
        return div(
            h2("Revenue"),
            p("Gross merchandise · demo series", className="hint"),
            raw(svg_bar_chart(d["labels"], d["revenue"], color=PALETTE[0])),
            className="card",
            
        )


class TrafficChart(Region):
    def render(self, ctx):
        d = _data()
        return div(
            h2("Visitors"),
            p("Unique sessions · demo series", className="hint"),
            raw(svg_line_chart(d["labels"], d["visitors"], color=PALETTE[1])),
            className="card",
            
        )


class MixChart(Region):
    def render(self, ctx):
        d = _data()
        mix = d["mix"]
        items = []
        for i, (name, pct) in enumerate(mix.items()):
            items.append(
                raw(
                    f'<li><span class="name"><span class="swatch" style="background:{PALETTE[i % len(PALETTE)]}"></span>'
                    f"{_esc(name)}</span><span class=\"pct\">{pct}%</span></li>"
                )
            )
        return div(
            h2("Traffic mix"),
            p("Source share for selected period", className="hint"),
            div(
                raw(svg_donut(mix)),
                raw("<ul class='legend'>" + "".join(
                    f'<li><span class="name"><span class="swatch" style="background:{PALETTE[i % len(PALETTE)]}"></span>'
                    f"{_esc(n)}</span><span class=\"pct\">{v}%</span></li>"
                    for i, (n, v) in enumerate(mix.items())
                ) + "</ul>"),
                className="donut-wrap",
            ),
            className="card",
            
        )


class Toolbar(Region):
    def render(self, ctx):
        return div(
            button(
                "Refresh sample",
                type="button",
                className="btn btn-primary",
                **ch.control(self.reshuffle).as_ux_dom(),
            ),
            button(
                "Reset to 7d",
                type="button",
                className="btn",
                **ch.control(self.reset).as_ux_dom(),
            ),
            className="actions",
            
        )

    @Region.action(refresh=["flash.bar", "kpi.row", "chart.revenue", "chart.traffic", "chart.mix"])
    def reshuffle(self):
        """Jitter current period series for demo interactivity."""
        p = _period()
        base = SERIES[p]
        jitter = lambda xs: [round(max(0.1, x * (0.92 + random.random() * 0.16)), 1) for x in xs]
        SERIES[p] = {
            **base,
            "revenue": jitter(base["revenue"]),
            "visitors": [int(x) for x in jitter([float(v) for v in base["visitors"]])],
        }
        ch.draft.set("flash", "Sample data refreshed")
        return None

    @Region.action(refresh=["flash.bar", "period.picker", "kpi.row", "chart.revenue", "chart.traffic", "chart.mix", "toolbar.main"])
    def reset(self):
        ch.draft.set("period", "7d")
        # restore original 7d
        SERIES["7d"] = {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "revenue": [12.4, 15.1, 13.8, 18.2, 21.0, 16.5, 19.4],
            "visitors": [820, 940, 880, 1100, 1320, 980, 1200],
            "mix": {"Organic": 42, "Paid": 28, "Referral": 18, "Direct": 12},
        }
        ch.draft.set("flash", "Reset to 7 days")
        return None


# Mount with stable explicit uids
# Our refresh lists used chart.revenue — align to actual uids
def _uids():
    return {
        "flash": flash.uid,
        "period": period.uid,
        "kpis": kpis.uid,
        "revenue": revenue.uid,
        "traffic": traffic.uid,
        "mix": mix.uid,
        "toolbar": toolbar.uid,
    }


# Re-register actions with correct refresh uids by patching — easier to set explicit uids on classes
# Override uids explicitly for stable wire names:
FlashBar.uid = "flash.bar"
PeriodPicker.uid = "period.picker"
KpiRow.uid = "kpi.row"
RevenueChart.uid = "chart.revenue"
TrafficChart.uid = "chart.traffic"
MixChart.uid = "chart.mix"
Toolbar.uid = "toolbar.main"

# Remount with explicit uids (use fresh instances)
flash = FlashBar(ch, uid="flash.bar").mount()
period = PeriodPicker(ch, uid="period.picker").mount()
kpis = KpiRow(ch, uid="kpi.row").mount()
revenue = RevenueChart(ch, uid="chart.revenue").mount()
traffic = TrafficChart(ch, uid="chart.traffic").mount()
mix = MixChart(ch, uid="chart.mix").mount()
toolbar = Toolbar(ch, uid="toolbar.main").mount()


@app.get("/", response_class=HTMLResponse)
def index():
    body = div(
        div(
            div(
                p("uxchannel · ux-dom", className="brand"),
                h1("Analytics"),
                p("Server-driven dashboard — regions morph without a full reload.", className="sub"),
            ),
            raw(period.html()),
            className="top",
        ),
        raw(flash.html()),
        raw(kpis.html()),
        div(
            raw(revenue.html()),
            raw(mix.html()),
            className="grid",
        ),
        div(raw(traffic.html()), style="margin-top:0.85rem"),
        raw(toolbar.html()),
        p("Period & refresh go through uxchannel actions + signed trust caps.", className="footer"),
        className="shell",
    )
    return HTMLResponse(str(document(body)))


# Export for tests
__all__ = ["app", "ch"]
