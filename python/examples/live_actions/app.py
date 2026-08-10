"""
Live Actions Console — demo app (NOT part of the uxchannel library).

Watches a Channel: catalog, regions, dispatch feed, success/fail stats.
ux-dom owns the document; uxchannel owns regions/actions.

  PYTHONPATH=src:/tmp/ux_dom:. uvicorn examples.live_actions.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Deque

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_dom import Document
from ux_dom.dom import button, div, h1, h2, p, raw

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.render.kit import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.host.catalog import action_catalog

app = FastAPI(title="uxchannel live actions demo")
SECRET = "live-actions-demo-secret-key-32b!!"
ch = Channel.boot(
    app,
    config=ChannelConfig.development(secret=SECRET, allow_memory_stores=True),
)

MAX_FEED = 80

@dataclass
class DispatchEvent:
    t: float
    action: str
    ok: bool
    duration_ms: float
    error: str = ""
    request_id: str = ""

@dataclass
class Telemetry:
    feed: Deque[DispatchEvent] = field(default_factory=lambda: deque(maxlen=MAX_FEED))
    by_action: Counter = field(default_factory=Counter)
    ok_count: int = 0
    err_count: int = 0
    total_ms: float = 0.0

    def record(self, ev: DispatchEvent) -> None:
        self.feed.appendleft(ev)
        self.by_action[ev.action] += 1
        if ev.ok:
            self.ok_count += 1
        else:
            self.err_count += 1
        self.total_ms += ev.duration_ms

    def clear(self) -> None:
        self.feed.clear()
        self.by_action.clear()
        self.ok_count = 0
        self.err_count = 0
        self.total_ms = 0.0

TEL = Telemetry()

@ch.after
def _tel_after(intent: Any, result: Any) -> Any:
    """Demo telemetry. After-hooks MUST return the Result (library replaces it)."""
    if result is None:
        return result
    action = str(getattr(intent, "action", "") or "")
    # clear_feed: handler already wiped TEL; do not re-record this meta action
    if action == "console.toolbar.clear_feed":
        return result
    # optional: still record domain + console fires (shows both). Prefer domain signal:
    # record everything except pure UI refresh
    if action == "console.toolbar.refresh_views":
        return result
    meta = getattr(result, "meta", None) or {}
    err = ""
    ok = bool(getattr(result, "ok", True))
    if not ok and getattr(result, "error", None):
        e = result.error
        err = getattr(e, "code", None) or str(e)
    TEL.record(
        DispatchEvent(
            t=time.time(),
            action=action or "?",
            ok=ok,
            duration_ms=float(meta.get("duration_ms") or 0),
            error=str(err),
            request_id=str(meta.get("request_id") or ""),
        )
    )
    return result


CART: dict[str, int] = {}

@ch.on(name="demo.ping", refresh=[
    "flash.bar", "kpi.strip", "action.catalog", "region.list",
    "dispatch.chart", "live.feed",
])
def demo_ping(msg: str = "pong"):
    ch.draft.set("flash", f"demo.ping → {msg}")
    return ch.done(notice=f"ping → {msg}")

@ch.on(name="demo.add_item", refresh=[
    "flash.bar", "kpi.strip", "action.catalog", "region.list",
    "dispatch.chart", "live.feed",
])
def demo_add_item(sku: str = "sku-a", qty: int = 1):
    CART[sku] = CART.get(sku, 0) + int(qty)
    ch.draft.set("flash", f"demo.add_item {sku}×{qty} (cart={CART[sku]})")
    return ch.done(notice=f"cart {sku}={CART[sku]}")

@ch.on(name="demo.fail", refresh=["flash.bar", "kpi.strip", "dispatch.chart", "live.feed"])
def demo_fail():
    ch.draft.set("flash", "demo.fail → validation error (see feed)")
    return ch.fail.valid({"x": ["intentional demo error"]}, message="demo fail")

@ch.on(name="demo.slow", refresh=[
    "flash.bar", "kpi.strip", "dispatch.chart", "live.feed",
])
def demo_slow():
    time.sleep(0.05)
    ch.draft.set("flash", "demo.slow finished")
    return ch.done(notice="slow ok")

PALETTE = ["#14b8a6", "#38bdf8", "#a78bfa", "#f472b6", "#fbbf24", "#fb923c"]
MUTED, GRID, INK = "#8b8b9a", "#26262f", "#e7e7ea"

def _esc(s: Any) -> str:
    t = str(s)
    for a, b in (("&", "&"+"amp;"), ("<", "&"+"lt;"), (">", "&"+"gt;"), (chr(34), "&"+"quot;")):
        t = t.replace(a, b)
    return t

def svg_bars(items: list[tuple[str, int]], *, width: int = 480, height: int = 160) -> str:
    if not items:
        return f'<p style="color:{MUTED};font-size:0.85rem">No dispatches yet — fire an action.</p>'
    pad_l, pad_r, pad_t, pad_b = 8, 8, 8, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max(v for _, v in items) or 1
    n = len(items)
    bw = plot_w / n
    bar_w = bw * 0.65
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" class="chart">']
    for i, (name, val) in enumerate(items):
        h = (val / vmax) * plot_h
        x = pad_l + i * bw + (bw - bar_w) / 2
        y = pad_t + plot_h - h
        color = PALETTE[i % len(PALETTE)]
        short = name.split(".")[-1][:10]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'rx="3" fill="{color}" opacity="0.9"><title>{_esc(name)}: {val}</title></rect>'
        )
        parts.append(
            f'<text x="{x + bar_w/2:.1f}" y="{height-8}" text-anchor="middle" '
            f'fill="{MUTED}" font-size="10" font-family="system-ui">{_esc(short)}</text>'
        )
        parts.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y-4:.1f}" text-anchor="middle" '
            f'fill="{INK}" font-size="10" font-family="system-ui">{val}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)

CSS = '\n:root {\n  --bg: #0b0b0f; --surface: #12121a; --surface2: #1a1a24;\n  --fg: #e7e7ea; --muted: #8b8b9a; --primary: #14b8a6;\n  --border: #26262f; --ok: #34d399; --err: #f87171; --radius: 12px;\n  --font: "DM Sans", system-ui, sans-serif;\n}\n* { box-sizing: border-box; }\nhtml, body { margin:0; min-height:100%; background:var(--bg); color:var(--fg);\n  font-family:var(--font); line-height:1.5; -webkit-font-smoothing:antialiased; }\nbutton:not(:disabled) { cursor:pointer; }\n.shell { max-width:1180px; margin:0 auto; padding:1.25rem 1rem 3rem; }\n.top { display:flex; flex-wrap:wrap; justify-content:space-between; gap:1rem;\n  align-items:flex-end; margin-bottom:1.25rem; }\n.brand { margin:0 0 .25rem; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }\nh1 { margin:0; font-size:clamp(1.4rem,3vw,1.8rem); font-weight:650; letter-spacing:-.02em; }\n.sub { margin:.3rem 0 0; color:var(--muted); font-size:.92rem; }\n.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:.65rem; margin-bottom:.9rem; }\n.kpi { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:.85rem 1rem; }\n.kpi .l { margin:0; font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }\n.kpi .v { margin:.2rem 0 0; font-size:1.35rem; font-weight:650; font-variant-numeric:tabular-nums; }\n.grid2 { display:grid; grid-template-columns:1.15fr .85fr; gap:.75rem; }\n.grid3 { display:grid; grid-template-columns:1fr 1fr; gap:.75rem; margin-top:.75rem; }\n@media (max-width:900px) { .grid2, .grid3 { grid-template-columns:1fr; } }\n.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);\n  padding:1rem 1.05rem; min-width:0; }\n.card h2 { margin:0 0 .15rem; font-size:.95rem; font-weight:600; }\n.hint { margin:0 0 .7rem; font-size:.8rem; color:var(--muted); }\ntable { width:100%; border-collapse:collapse; font-size:.82rem; }\nth, td { text-align:left; padding:.4rem .35rem; border-bottom:1px solid var(--border);\n  vertical-align:top; font-variant-numeric:tabular-nums; }\nth { color:var(--muted); font-weight:500; font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; }\ntr:hover td { background:rgba(255,255,255,.02); }\n.mono { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.78rem; }\n.tag { display:inline-block; padding:.1rem .4rem; border-radius:4px; font-size:.72rem; font-weight:600; }\n.tag-ok { background:rgba(52,211,153,.15); color:var(--ok); }\n.tag-err { background:rgba(248,113,113,.15); color:var(--err); }\n.tag-async { background:rgba(56,189,248,.12); color:#38bdf8; }\n.tag-sync { background:rgba(167,139,250,.12); color:#a78bfa; }\n.actions { display:flex; flex-wrap:wrap; gap:.45rem; }\n.btn { border:1px solid var(--border); background:var(--surface2); color:var(--fg);\n  font:inherit; font-size:.85rem; font-weight:500; padding:.5rem .9rem; border-radius:8px; min-height:42px; }\n.btn:hover { border-color:var(--primary); }\n.btn-primary { background:var(--primary); border-color:var(--primary); color:#042f2e; font-weight:600; }\n.btn-danger { border-color:rgba(248,113,113,.4); color:var(--err); }\n.feed { max-height:320px; overflow:auto; }\n.flash { margin:0 0 .85rem; padding:.55rem .85rem; border-radius:8px;\n  background:rgba(20,184,166,.12); color:var(--primary); font-size:.88rem;\n  border:1px solid rgba(20,184,166,.25); min-height:1em; }\n.flash:empty { display:none; }\n.footer { margin-top:1.75rem; color:var(--muted); font-size:.78rem; }\n.chart { display:block; max-width:100%; }\n.pill { display:inline-flex; gap:.35rem; flex-wrap:wrap; }\n.pill span { background:var(--surface2); border:1px solid var(--border); border-radius:999px;\n  padding:.15rem .55rem; font-size:.75rem; color:var(--muted); }\n'

document = Document(
    head=[
        raw(
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
            '<title>Live Actions · uxchannel demo</title>'
            '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>'
            f"<style>{CSS}</style>"
        ),
        raw(str(demo_scripts(ch, ))),
        # ux-dom renders bare <body>; stamp channel endpoint attrs for the client.
        raw(
            "<script>(function(){function a(){var b=document.body;if(!b)return;"
            "b.setAttribute('data-channel-endpoint','/ux-channel/action');"
            "b.setAttribute('data-channel-dev','');"
            "}if(document.body)a();else document.addEventListener('DOMContentLoaded',a);})();</script>"
        ),
    ]
)

class FlashBar(Region):
    def render(self, ctx):
        return div(ch.draft.get("flash") or "", className="flash")

class KpiStrip(Region):
    def render(self, ctx):
        diag = ch.diagnose()
        total = TEL.ok_count + TEL.err_count
        avg = (TEL.total_ms / total) if total else 0.0
        cards = [
            ("Actions", str(diag.get("actions", 0))),
            ("Regions", str(len(diag.get("regions") or []))),
            ("Dispatches", str(total)),
            ("OK", str(TEL.ok_count)),
            ("Errors", str(TEL.err_count)),
            ("Avg ms", f"{avg:.1f}"),
        ]
        return div(
            *[div(p(lab, className="l"), p(val, className="v"), className="kpi") for lab, val in cards],
            className="kpis",
        )

class ActionCatalog(Region):
    def render(self, ctx):
        rows = []
        for item in action_catalog(ch.registry):
            kind = "async" if item.get("async") else "sync"
            params = ", ".join(p["name"] for p in item.get("params") or []) or "—"
            doc = item.get("doc") or ""
            rows.append(
                "<tr>"
                f'<td class="mono">{_esc(item["name"])}</td>'
                f'<td><span class="tag tag-{kind}">{kind}</span></td>'
                f'<td class="mono">{_esc(params)}</td>'
                f"<td>{_esc(doc)}</td>"
                "</tr>"
            )
        body = "".join(rows) or '<tr><td colspan="4">No actions registered</td></tr>'
        return div(
            h2("Action catalog"),
            p("Live from action_catalog(ch.registry)", className="hint"),
            raw(
                "<table><thead><tr><th>Name</th><th>Kind</th><th>Params</th><th>Doc</th></tr></thead><tbody>"
                + body + "</tbody></table>"
            ),
            className="card",
        )

class RegionList(Region):
    def render(self, ctx):
        uids = sorted(ch.regions.uids())
        pills = "".join(f"<span class='mono'>{_esc(u)}</span>" for u in uids) or "<span>none</span>"
        diag = ch.diagnose()
        meta = (
            f"env={diag.get('environment')} · path={diag.get('path')} · "
            f"require_cap={diag.get('require_cap')} · state={diag.get('state')}"
        )
        return div(
            h2("Regions + diagnose"),
            p(meta, className="hint"),
            raw(f'<div class="pill">{pills}</div>'),
            className="card",
        )

class DispatchChart(Region):
    def render(self, ctx):
        items = sorted(TEL.by_action.items(), key=lambda x: (-x[1], x[0]))[:12]
        return div(
            h2("Dispatches by action"),
            p("Counts since process start (or last clear)", className="hint"),
            raw(svg_bars(items)),
            className="card",
        )

class LiveFeed(Region):
    def render(self, ctx):
        rows = []
        for ev in list(TEL.feed)[:40]:
            tag = "ok" if ev.ok else "err"
            label = "ok" if ev.ok else (ev.error or "err")
            ts = time.strftime("%H:%M:%S", time.localtime(ev.t))
            rows.append(
                "<tr>"
                f'<td class="mono">{ts}</td>'
                f'<td class="mono">{_esc(ev.action)}</td>'
                f'<td><span class="tag tag-{tag}">{_esc(label)}</span></td>'
                f"<td>{ev.duration_ms:.1f}</td>"
                f'<td class="mono">{_esc(ev.request_id[:12])}</td>'
                "</tr>"
            )
        body = "".join(rows) or '<tr><td colspan="5">Feed empty — invoke an action</td></tr>'
        return div(
            h2("Live dispatch feed"),
            p("Populated by @ch.after — newest first", className="hint"),
            raw(
                '<div class="feed"><table><thead><tr>'
                "<th>Time</th><th>Action</th><th>Result</th><th>ms</th><th>req</th>"
                "</tr></thead><tbody>" + body + "</tbody></table></div>"
            ),
            className="card",
        )

REFRESH_ALL = [
    "flash.bar", "kpi.strip", "action.catalog", "region.list",
    "dispatch.chart", "live.feed", "console.toolbar",
]

class ConsoleToolbar(Region):
    def render(self, ctx):
        # Wire demo.* actions directly — one Intent per click (clean feed).
        return div(
            button(
                "Ping",
                type="button",
                className="btn btn-primary",
                **ch.control("demo.ping", trust_msg="from-console").as_ux_dom(),
            ),
            button(
                "Add item",
                type="button",
                className="btn",
                **ch.control("demo.add_item", trust_sku="sku-a").as_ux_dom(),
            ),
            button(
                "Demo fail",
                type="button",
                className="btn btn-danger",
                **ch.control("demo.fail").as_ux_dom(),
            ),
            button(
                "Slow",
                type="button",
                className="btn",
                **ch.control("demo.slow").as_ux_dom(),
            ),
            button(
                "Refresh views",
                type="button",
                className="btn",
                **ch.control(self.refresh_views).as_ux_dom(),
            ),
            button(
                "Clear feed",
                type="button",
                className="btn",
                **ch.control(self.clear_feed).as_ux_dom(),
            ),
            className="actions",
        )

    @Region.action
    def refresh_views(self):
        ch.draft.set("flash", "Views refreshed")
        return ch.done(refresh=REFRESH_ALL)

    @Region.action
    def clear_feed(self):
        TEL.clear()
        ch.draft.set("flash", "Telemetry cleared")
        return ch.done(refresh=REFRESH_ALL)



flash = FlashBar(ch, uid="flash.bar").mount()
kpis = KpiStrip(ch, uid="kpi.strip").mount()
catalog = ActionCatalog(ch, uid="action.catalog").mount()
regions = RegionList(ch, uid="region.list").mount()
chart = DispatchChart(ch, uid="dispatch.chart").mount()
feed = LiveFeed(ch, uid="live.feed").mount()
toolbar = ConsoleToolbar(ch, uid="console.toolbar").mount()

@app.get("/", response_class=HTMLResponse)
def index():
    body = div(
        div(
            div(
                p("demo app · not the library", className="brand"),
                h1("Live actions"),
                p("Catalog, regions, and every dispatch — ux-dom + uxchannel regions.", className="sub"),
            ),
            raw(toolbar.html()),
            className="top",
        ),
        raw(flash.html()),
        raw(kpis.html()),
        div(raw(catalog.html()), raw(regions.html()), className="grid2"),
        div(raw(chart.html()), raw(feed.html()), className="grid3"),
        p("Telemetry is process-local demo state via @ch.after — not shipped inside ux-channel.", className="footer"),
        className="shell",
    )
    return HTMLResponse(str(document(body)))

__all__ = ["app", "ch", "TEL"]
