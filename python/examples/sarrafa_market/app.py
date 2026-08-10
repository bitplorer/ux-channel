"""
Sarrafa Market Tracker — ux-dom + uxchannel Live-style board for Indian bullion / jewellery market rates:
  • 24K / 22K / 18K gold (₹/g)
  • Silver (₹/g)
  • City board (Lucknow, Delhi, Mumbai, …)
  • Making-charge jewellery calculator
  • Tick history sparklines (SVG, no npm required)

Simulated walk for demo (swap loaders for real API/DB later).

Run:
  PYTHONPATH=src:/tmp/ux_dom uvicorn examples.sarrafa_market.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig, Region, Result
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

app = FastAPI(title="Sarrafa Market · ux-channel")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
    ),
)

CITIES = {
    "lucknow": {"name": "Lucknow", "premium": 0.0},
    "delhi": {"name": "Delhi", "premium": 8.0},
    "mumbai": {"name": "Mumbai", "premium": 12.0},
    "jaipur": {"name": "Jaipur", "premium": -5.0},
    "kolkata": {"name": "Kolkata", "premium": 3.0},
    "chennai": {"name": "Chennai", "premium": 6.0},
}

# Spot baselines (₹/g) — illustrative demo numbers, not live exchange quotes
BASE = {"gold_24": 7450.0, "silver": 92.5}


def _now() -> str:
    return datetime.now().strftime("%d %b %Y · %I:%M:%S %p")


def _market() -> dict[str, Any]:
    m = ch.draft.get("market")
    if not m:
        g = BASE["gold_24"]
        s = BASE["silver"]
        m = {
            "city": "lucknow",
            "gold_24": g,
            "gold_22": round(g * 22 / 24, 2),
            "gold_18": round(g * 18 / 24, 2),
            "silver": s,
            "prev_gold": g,
            "prev_silver": s,
            "history_gold": [g + random.uniform(-40, 40) for _ in range(24)],
            "history_silver": [s + random.uniform(-2, 2) for _ in range(24)],
            "ticks": 0,
            "updated": _now(),
            "trend": "flat",
            # calculator
            "calc_metal": "gold_22",
            "calc_grams": 10.0,
            "calc_making_pct": 12.0,
            "calc_gst_pct": 3.0,
        }
        m["history_gold"][-1] = g
        m["history_silver"][-1] = s
        ch.draft.set("market", m)
    return m


def _apply_city(m: dict[str, Any]) -> dict[str, float]:
    prem = CITIES[m["city"]]["premium"]
    g = m["gold_24"] + prem
    return {
        "gold_24": round(g, 2),
        "gold_22": round(g * 22 / 24, 2),
        "gold_18": round(g * 18 / 24, 2),
        "silver": round(m["silver"] + prem * 0.02, 2),
    }


def _sparkline(values: list[float], *, color: str, w: int = 160, h: int = 48) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pad = 3
    pts = []
    n = len(values)
    for i, v in enumerate(values):
        x = pad + i * (w - 2 * pad) / max(n - 1, 1)
        y = h - pad - (v - lo) / span * (h - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    last = values[-1]
    first = values[0]
    up = last >= first
    fill = color if up else "#f43f5e"
    return f"""
    <svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">
      <polyline fill="none" stroke="{fill}" stroke-width="2" stroke-linecap="round"
        stroke-linejoin="round" points="{poly}"/>
    </svg>"""


def _delta(cur: float, prev: float) -> tuple[str, str]:
    d = cur - prev
    pct = (d / prev * 100) if prev else 0.0
    cls = "up" if d > 0 else ("down" if d < 0 else "flat")
    sign = "+" if d > 0 else ""
    return cls, f"{sign}{d:.2f} ({sign}{pct:.2f}%)"


def _inr(n: float) -> str:
    # Indian grouping-ish simple format
    return f"₹{n:,.2f}"


def _calc(m: dict[str, Any]) -> dict[str, float]:
    rates = _apply_city(m)
    metal = m["calc_metal"]
    rate = rates.get(metal, rates["gold_22"])
    grams = float(m["calc_grams"])
    making_pct = float(m["calc_making_pct"])
    gst_pct = float(m["calc_gst_pct"])
    metal_cost = rate * grams
    making = metal_cost * making_pct / 100
    sub = metal_cost + making
    gst = sub * gst_pct / 100
    total = sub + gst
    return {
        "rate": rate,
        "metal_cost": metal_cost,
        "making": making,
        "gst": gst,
        "total": total,
        "grams": grams,
    }


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------


class Ticker(Region):
    def render(self, ctx):
        m = _market()
        rates = _apply_city(m)
        city = CITIES[m["city"]]["name"]
        gcls, gdel = _delta(rates["gold_24"], m["prev_gold"] + CITIES[m["city"]]["premium"])
        scls, sdel = _delta(rates["silver"], m["prev_silver"])
        return f"""
        <div data-channel-id="{self.uid}" class="ticker">
          <div class="tick-item">
            <span class="tick-label">24K Gold · {city}</span>
            <span class="tick-price">{_inr(rates["gold_24"])}<small>/g</small></span>
            <span class="delta {gcls}">{gdel}</span>
          </div>
          <div class="tick-item">
            <span class="tick-label">22K Gold</span>
            <span class="tick-price">{_inr(rates["gold_22"])}<small>/g</small></span>
          </div>
          <div class="tick-item">
            <span class="tick-label">18K Gold</span>
            <span class="tick-price">{_inr(rates["gold_18"])}<small>/g</small></span>
          </div>
          <div class="tick-item">
            <span class="tick-label">Silver</span>
            <span class="tick-price">{_inr(rates["silver"])}<small>/g</small></span>
            <span class="delta {scls}">{sdel}</span>
          </div>
          <div class="tick-meta">
            <span class="live-dot"></span> Simulated live · {m["updated"]}
            · ticks {m["ticks"]}
          </div>
        </div>
        """


class RateBoard(Region):
    def render(self, ctx):
        m = _market()
        rates = _apply_city(m)
        city = CITIES[m["city"]]["name"]
        cards = []
        rows = [
            ("24K Pure", rates["gold_24"], m["history_gold"], "#fbbf24"),
            ("22K Hallmark", rates["gold_22"], [x * 22 / 24 for x in m["history_gold"]], "#f59e0b"),
            ("18K Jewellery", rates["gold_18"], [x * 18 / 24 for x in m["history_gold"]], "#d97706"),
            ("Silver", rates["silver"], m["history_silver"], "#94a3b8"),
        ]
        for title, price, hist, color in rows:
            cards.append(
                f"""
            <article class="rate-card">
              <header>
                <h3>{title}</h3>
                <span class="city-pill">{city}</span>
              </header>
              <div class="rate-main">{_inr(price)}<small> / gram</small></div>
              <div class="rate-sub">10g · {_inr(price * 10)} · 1 tola (11.66g) · {_inr(price * 11.664)}</div>
              {_sparkline(hist, color=color)}
            </article>
            """
            )
        return f'<div data-channel-id="{self.uid}" class="rate-grid">{"".join(cards)}</div>'


class CityBar(Region):
    def render(self, ctx):
        m = _market()
        btns = []
        for key, info in CITIES.items():
            active = "active" if m["city"] == key else ""
            # each city button is a control
            d = ch.control(set_city, trust_city=key).as_dict()
            attrs = " ".join(f'{k}="{v}"' for k, v in d.items())
            btns.append(
                f'<button type="button" class="city-btn {active}" {attrs}>{info["name"]}</button>'
            )
        return f'<div data-channel-id="{self.uid}" class="city-bar">{"".join(btns)}</div>'


class Calculator(Region):
    def render(self, ctx):
        m = _market()
        c = _calc(m)
        metal = m["calc_metal"]
        options = [
            ("gold_24", "24K Gold"),
            ("gold_22", "22K Gold"),
            ("gold_18", "18K Gold"),
            ("silver", "Silver"),
        ]
        opt_parts = []
        for k, lab in options:
            sel = " selected" if metal == k else ""
            opt_parts.append(f'<option value="{k}"{sel}>{lab}</option>')
        opts = "".join(opt_parts)
        # form fields use free args (not trust) — signed empty trust, form merges carefully;
        # we use dedicated actions with trust for metal and numeric from form.
        return f"""
        <div data-channel-id="{self.uid}" class="calc panel">
          <h2>Jewellery estimate</h2>
          <p class="hint">Rate × weight + making % + GST — hallmark board style</p>
          <div class="calc-grid">
            <label>Metal
              <select id="calc-metal" data-channel-field="metal">
                {opts}
              </select>
            </label>
            <label>Weight (grams)
              <input id="calc-grams" type="number" step="0.01" min="0.1"
                value="{m["calc_grams"]}" data-channel-field="grams"/>
            </label>
            <label>Making charge %
              <input id="calc-making" type="number" step="0.5" min="0"
                value="{m["calc_making_pct"]}" data-channel-field="making_pct"/>
            </label>
            <label>GST %
              <input id="calc-gst" type="number" step="0.5" min="0"
                value="{m["calc_gst_pct"]}" data-channel-field="gst_pct"/>
            </label>
          </div>
          <button type="button" class="btn primary" id="calc-run"
            {ch.control(run_calc)}>
            Recalculate
          </button>
          <div class="calc-result">
            <div><span>Metal</span><strong>{_inr(c["metal_cost"])}</strong></div>
            <div><span>Making</span><strong>{_inr(c["making"])}</strong></div>
            <div><span>GST</span><strong>{_inr(c["gst"])}</strong></div>
            <div class="total"><span>Customer total</span><strong>{_inr(c["total"])}</strong></div>
          </div>
        </div>
        """


class Pulse(Region):
    def render(self, ctx):
        m = _market()
        trend = m.get("trend", "flat")
        emoji = {"up": "▲ bullish", "down": "▼ soft", "flat": "● steady"}.get(trend, "●")
        return f"""
        <div data-channel-id="{self.uid}" class="pulse">
          <div class="pulse-title">Market pulse</div>
          <div class="pulse-trend {trend}">{emoji}</div>
          <p>Demo feed walks randomly around a Lucknow-style board.
          Wire <code>refresh_rates</code> to your bullion API or DB loader later.</p>
        </div>
        """


ticker = ch.use(Ticker, uid="board.ticker")
board = ch.use(RateBoard, uid="board.rates")
cities = ch.use(CityBar, uid="board.cities")
calc = ch.use(Calculator, uid="board.calc")
pulse = ch.use(Pulse, uid="board.pulse")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@ch.on(name="Market.tick", refresh=[ticker, board, pulse, calc])
def tick_market():
    """One simulated market tick (random walk)."""
    m = _market()
    m["prev_gold"] = m["gold_24"]
    m["prev_silver"] = m["silver"]
    dg = random.uniform(-28, 32)
    ds = random.uniform(-1.2, 1.3)
    m["gold_24"] = max(5000.0, m["gold_24"] + dg)
    m["silver"] = max(40.0, m["silver"] + ds)
    m["gold_22"] = round(m["gold_24"] * 22 / 24, 2)
    m["gold_18"] = round(m["gold_24"] * 18 / 24, 2)
    m["history_gold"] = (m["history_gold"] + [m["gold_24"]])[-24:]
    m["history_silver"] = (m["history_silver"] + [m["silver"]])[-24:]
    m["ticks"] = int(m["ticks"]) + 1
    m["updated"] = _now()
    if dg > 3:
        m["trend"] = "up"
    elif dg < -3:
        m["trend"] = "down"
    else:
        m["trend"] = "flat"
    ch.draft.set("market", m)
    return ch.done(notice=f"Board updated · {_inr(_apply_city(m)['gold_24'])}/g 24K")


@ch.on(name="Market.city", refresh=[ticker, board, cities, calc])
def set_city(city: str = "lucknow"):
    if city not in CITIES:
        return ch.fail.valid({"city": ["unknown city"]})
    m = _market()
    m["city"] = city
    m["updated"] = _now()
    ch.draft.set("market", m)
    return ch.done(notice=f"City → {CITIES[city]['name']}")


@ch.on(name="Market.calc", refresh=[calc])
def run_calc(
    metal: str = "gold_22",
    grams: float = 10.0,
    making_pct: float = 12.0,
    gst_pct: float = 3.0,
):
    m = _market()
    if metal not in ("gold_24", "gold_22", "gold_18", "silver"):
        metal = "gold_22"
    try:
        grams = max(0.1, float(grams))
        making_pct = max(0.0, float(making_pct))
        gst_pct = max(0.0, float(gst_pct))
    except (TypeError, ValueError):
        return ch.fail.valid({"grams": ["invalid"]})
    m["calc_metal"] = metal
    m["calc_grams"] = grams
    m["calc_making_pct"] = making_pct
    m["calc_gst_pct"] = gst_pct
    ch.draft.set("market", m)
    total = _calc(m)["total"]
    return ch.done(notice=f"Estimate {_inr(total)}")


@ch.on(name="Market.reset", refresh=[ticker, board, pulse, calc, cities])
def reset_board():
    ch.draft.clear("market")
    _market()
    return ch.done(notice="Board reset to baseline")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #120c08;
  --bg2: #1a120c;
  --panel: #221710;
  --ink: #f8f1e3;
  --muted: #b9a48a;
  --gold: #f5c451;
  --gold2: #d4a017;
  --line: rgba(245,196,81,.14);
  --up: #34d399;
  --down: #fb7185;
  --radius: 16px;
  font-family: "Segoe UI", "Noto Sans Devanagari", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; color: var(--ink);
  background:
    radial-gradient(900px 500px at 10% -10%, #3a2910 0%, transparent 55%),
    radial-gradient(800px 400px at 100% 0%, #2a1810 0%, transparent 50%),
    linear-gradient(180deg, #0c0907, var(--bg));
}
.wrap { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1.15rem 3rem; }
.brand {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap; margin-bottom: 1.25rem;
}
.brand h1 {
  margin: 0; font-size: 1.75rem; letter-spacing: -.02em;
  background: linear-gradient(90deg, #fff7e0, var(--gold), #b45309);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.brand .sub { margin: .35rem 0 0; color: var(--muted); max-width: 28rem; line-height: 1.45; }
.badge-row { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .6rem; }
.badge-row span {
  font-size: .7rem; border: 1px solid var(--line); color: var(--muted);
  padding: .15rem .5rem; border-radius: 999px; background: rgba(0,0,0,.25);
}
.toolbar { display: flex; flex-wrap: wrap; gap: .5rem; }
button, .btn {
  appearance: none; cursor: pointer; border: 1px solid var(--line);
  background: rgba(245,196,81,.08); color: var(--ink);
  border-radius: 999px; padding: .55rem 1rem; font-weight: 600; font-size: .88rem;
}
button:hover, .btn:hover { border-color: rgba(245,196,81,.45); background: rgba(245,196,81,.16); }
.btn.primary, button.primary {
  background: linear-gradient(135deg, #f5c451, #b45309);
  color: #1a1008; border-color: transparent;
}
.ticker {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: .65rem; margin-bottom: .5rem;
  background: linear-gradient(180deg, rgba(245,196,81,.07), transparent), var(--panel);
  border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem;
}
@media (max-width: 800px) { .ticker { grid-template-columns: repeat(2, 1fr); } }
.tick-item { display: flex; flex-direction: column; gap: .2rem; }
.tick-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.tick-price { font-size: 1.25rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.tick-price small { font-size: .75rem; font-weight: 600; color: var(--muted); margin-left: .2rem; }
.delta { font-size: .8rem; font-weight: 700; }
.delta.up { color: var(--up); } .delta.down { color: var(--down); } .delta.flat { color: var(--muted); }
.tick-meta {
  grid-column: 1 / -1; display: flex; align-items: center; gap: .45rem;
  font-size: .78rem; color: var(--muted); margin-top: .25rem;
}
.live-dot {
  width: .55rem; height: .55rem; border-radius: 50%; background: var(--up);
  box-shadow: 0 0 0 0 rgba(52,211,153,.6); animation: pulse 1.6s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(52,211,153,.55); }
  70% { box-shadow: 0 0 0 8px rgba(52,211,153,0); }
  100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}
.city-bar {
  display: flex; flex-wrap: wrap; gap: .4rem; margin: .85rem 0 1rem;
}
.city-btn {
  font-size: .8rem; padding: .4rem .85rem;
  background: rgba(0,0,0,.25);
}
.city-btn.active {
  background: linear-gradient(135deg, #f5c451, #b45309);
  color: #1a1008; border-color: transparent;
}
.rate-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: .85rem;
}
@media (max-width: 720px) { .rate-grid { grid-template-columns: 1fr; } }
.rate-card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 1rem 1.1rem;
}
.rate-card header { display: flex; justify-content: space-between; align-items: center; }
.rate-card h3 { margin: 0; font-size: 1rem; }
.city-pill {
  font-size: .68rem; color: var(--gold); border: 1px solid var(--line);
  padding: .15rem .45rem; border-radius: 999px;
}
.rate-main { font-size: 1.55rem; font-weight: 800; margin: .45rem 0 .2rem; color: var(--gold); }
.rate-main small { font-size: .85rem; color: var(--muted); font-weight: 600; }
.rate-sub { font-size: .78rem; color: var(--muted); margin-bottom: .5rem; }
.spark { display: block; width: 100%; height: 48px; }
.layout {
  display: grid; grid-template-columns: 1.4fr .9fr; gap: 1rem; margin-top: 1rem;
}
@media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
.panel {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 1.1rem 1.15rem;
}
.panel h2 { margin: 0 0 .25rem; font-size: 1.1rem; }
.hint { margin: 0 0 1rem; color: var(--muted); font-size: .85rem; }
.calc-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: .65rem; margin-bottom: .85rem;
}
label { display: flex; flex-direction: column; gap: .3rem; font-size: .78rem; color: var(--muted); }
input, select {
  background: #140e0a; border: 1px solid var(--line); color: var(--ink);
  border-radius: 10px; padding: .55rem .65rem; font-size: .95rem;
}
.calc-result {
  margin-top: 1rem; display: grid; gap: .45rem;
  border-top: 1px solid var(--line); padding-top: .85rem;
}
.calc-result div { display: flex; justify-content: space-between; font-size: .92rem; }
.calc-result .total { font-size: 1.1rem; color: var(--gold); margin-top: .25rem; }
.pulse-title { font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.pulse-trend { font-size: 1.35rem; font-weight: 800; margin: .4rem 0; }
.pulse-trend.up { color: var(--up); } .pulse-trend.down { color: var(--down); }
.pulse p { margin: 0; color: var(--muted); font-size: .85rem; line-height: 1.45; }
.pulse code { color: var(--gold); }
.foot { margin-top: 1.5rem; color: var(--muted); font-size: .78rem; }
"""

CALC_JS = """
<script>
(function () {
  function wireCalc() {
    var btn = document.getElementById('calc-run');
    if (!btn || btn._sarrafaWired) return;
    btn._sarrafaWired = true;
    btn.addEventListener('click', function () {
      var metal = (document.getElementById('calc-metal') || {}).value || 'gold_22';
      var grams = (document.getElementById('calc-grams') || {}).value || '10';
      var making = (document.getElementById('calc-making') || {}).value || '12';
      var gst = (document.getElementById('calc-gst') || {}).value || '3';
      // merge into data-channel-args for this click
      var args = {metal: metal, grams: Number(grams), making_pct: Number(making), gst_pct: Number(gst)};
      btn.setAttribute('data-channel-args', JSON.stringify(args));
    }, true);
  }
  document.addEventListener('DOMContentLoaded', wireCalc);
  // re-wire after morphs
  document.addEventListener('uid:after-apply', wireCalc);
  setInterval(wireCalc, 800);
})();
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
    try:
        from ux_dom import Document
        from ux_dom.dom import div, h1, p, raw, span

        doc = Document(
            head=[
                raw('<meta charset="utf-8">'),
                raw('<meta name="viewport" content="width=device-width,initial-scale=1">'),
                raw("<title>Sarrafa Market · Lucknow board</title>"),
                raw(f"<style>{CSS}</style>"),
                raw(scripts),
                raw(CALC_JS),
            ]
        )
        page = div(
            div(
                div(
                    div(
                        span("ux-dom"),
                        span("ux-channel"),
                        span("सर्राफ़ा board"),
                        className="badge-row",
                    ),
                    h1("Sarrafa Market"),
                    p(
                        "Hallmark-style bullion board for jewellery shops — "
                        "city premiums, karat rates, and making-charge estimates. "
                        "Rates are simulated; actions morph live regions."
                    ),
                ),
                div(
                    raw(_btn("⟳ Tick market", tick_market, primary=True)),
                    raw(_btn("Reset board", reset_board)),
                    className="toolbar",
                ),
                className="brand",
            ),
            raw(ticker()),
            raw(cities()),
            raw(board()),
            div(
                raw(calc()),
                raw(pulse()),
                className="layout",
            ),
            p(
                "Demo · swap Market.tick loader for your feed · uxchannel 0.1",
                className="foot",
            ),
            className="wrap",
        )
        html = str(doc(page))
        if "<body" in html:
            html = html.replace("<body", f"<body {attr_string(ch.body_attrs())}", 1)
        else:
            html = f"<!doctype html><html><body {attr_string(ch.body_attrs())}>{html}</body></html>"
        return HTMLResponse(html)
    except ImportError:
        return HTMLResponse(
            f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sarrafa Market</title><style>{CSS}</style>{scripts}{CALC_JS}</head>
<body {attr_string(ch.body_attrs())}>
<div class="wrap">
  <div class="brand">
    <div>
      <div class="badge-row"><span>ux-channel</span><span>Sarrafa</span></div>
      <h1>Sarrafa Market</h1>
      <p class="sub">Bullion board + jewellery calculator</p>
    </div>
    <div class="toolbar">
      {_btn("Tick market", tick_market, primary=True)}
      {_btn("Reset board", reset_board)}
    </div>
  </div>
  {ticker()}{cities()}{board()}
  <div class="layout">{calc()}{pulse()}</div>
</div></body></html>"""
        )


@app.get("/health")
def health():
    m = _market()
    return {"ok": True, "city": m["city"], "gold_24": m["gold_24"], "ticks": m["ticks"]}
