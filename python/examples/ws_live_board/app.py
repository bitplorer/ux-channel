"""
WebSocket usability demo — ux-dom + uxchannel Shows production-style WS duplex:
  • Auto-connect via data-channel-ws + ticket/public topics
  • Multi-topic live morphs (ticker, tape, status) over one socket
  • Intent over WebSocket (caps) — bump / pause / shout
  • Same PushBus as SSE — feeder publishes Results

Run:
  PYTHONPATH=src:/tmp/ux_dom uvicorn examples.ws_live_board.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_dom.dom import button, div, h1, h2, p, raw, span

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.render.kit import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.transport.push import get_push_bus
from ux_channel.protocol.types import Result

log = logging.getLogger("ws_live_board")

SECRET = "ws-demo-secret-key-32chars-min!!!!"
TOPIC_TICKER = "public.ws.ticker"
TOPIC_TAPE = "public.ws.tape"
TOPIC_STATUS = "public.ws.status"
TOPIC_CONTROLS = "public.ws.controls"
# Private-style topic (authorized by ticket on the page)
TOPIC_PRIVATE = "shop.ws.pulse"


def _state() -> dict[str, Any]:
    s = ch.draft.get("ws_demo")
    if not s:
        gold, silver = 7450.0, 92.5
        s = {
            "running": True,
            "gold": gold,
            "silver": silver,
            "ticks": 0,
            "shouts": [],
            "last_event": "boot",
            "conn_hint": "WebSocket duplex — multi-topic + actions",
            "private_n": 0,
            "history_g": [gold] * 16,
            "history_s": [silver] * 16,
        }
        ch.draft.set("ws_demo", s)
    return s


def _save(s: dict[str, Any]) -> None:
    """Persist draft snapshot (replace whole blob — avoid lost concurrent keys)."""
    ch.draft.set("ws_demo", s)


def _inr(n: float) -> str:
    return f"₹{n:,.2f}"


def _spark(vals: list[float], color: str, w: int = 220, h: int = 40) -> str:
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
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" class="spark" aria-hidden="true">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" points="{" ".join(pts)}"/></svg>'
    )


def _push(*uids: str, topic: str | None = None) -> None:
    """Publish a multi-region Result so all WS/SSE clients morph (not only the clicker)."""
    result = ch.refresh(*uids)
    if not isinstance(result, Result) or not result.ops:
        return
    bus = get_push_bus()
    if topic:
        bus.publish(topic, result)
        return
    # fan-out: map primary region → topic so subscribers of any topic get updates
    for uid in uids:
        t = {
            "ws.ticker": TOPIC_TICKER,
            "ws.tape": TOPIC_TAPE,
            "ws.status": TOPIC_STATUS,
            "ws.controls": TOPIC_CONTROLS,
            "ws.private": TOPIC_PRIVATE,
        }.get(uid)
        if t:
            # each topic gets full multi-morph result (idempotent morphs)
            bus.publish(t, result)


# ── Regions ──────────────────────────────────────────────────────────────
# Do NOT put data-channel-id on roots — ch.html / ch.refresh wrap already.


class Ticker(Region):
    def render(self, ctx):
        s = _state()
        hist_g = s.get("history_g") or [s["gold"]] * 16
        hist_s = s.get("history_s") or [s["silver"]] * 16
        return div(
            {"class": "card ticker"},
            div({"class": "row"}, h2("Live ticker"), span({"class": "pill"}, "WS topic")),
            div(
                {"class": "prices"},
                div(
                    {"class": "price gold"},
                    span({"class": "lbl"}, "Gold"),
                    span({"class": "val"}, _inr(s["gold"])),
                    raw(_spark(hist_g, "#e8b84a")),
                ),
                div(
                    {"class": "price silver"},
                    span({"class": "lbl"}, "Silver"),
                    span({"class": "val"}, _inr(s["silver"])),
                    raw(_spark(hist_s, "#9aa7b8")),
                ),
            ),
            p({"class": "meta"}, f"ticks {s['ticks']} · {s.get('last_event', '—')}"),
        )


class Tape(Region):
    def render(self, ctx):
        s = _state()
        shouts = s.get("shouts") or []
        items = []
        for sh in shouts[:12]:
            # Plain text only — ux-dom escapes; do not pre-escape (double-entity bug)
            items.append(
                div(
                    {"class": "tape-line"},
                    span({"class": "t"}, sh.get("t", "")),
                    span({"class": "m"}, str(sh.get("msg", ""))),
                )
            )
        if not items:
            items = [p({"class": "empty"}, "Shouts & feeder events appear here over WebSocket…")]
        return div(
            {"class": "card tape"},
            div({"class": "row"}, h2("Event tape"), span({"class": "pill"}, TOPIC_TAPE)),
            div({"class": "tape-body"}, *items),
        )


class LinkStatus(Region):
    def render(self, ctx):
        s = _state()
        run = s.get("running", True)
        return div(
            {"class": "card status"},
            div({"class": "row"}, h2("Channel status"), span(
                {"class": "pill " + ("on" if run else "off")},
                "FEEDER ON" if run else "FEEDER PAUSED",
            )),
            p(s.get("conn_hint", "")),
            p({"class": "meta"}, f"private pulse count: {s.get('private_n', 0)}"),
            p(
                {"class": "meta mono"},
                f"topics: {TOPIC_TICKER}, {TOPIC_TAPE}, {TOPIC_STATUS}, {TOPIC_CONTROLS}",
            ),
        )


class PrivatePulse(Region):
    """Region on a ticket-gated topic — proves private subscribe over WS."""

    def render(self, ctx):
        s = _state()
        n = s.get("private_n", 0)
        return div(
            {"class": "card private"},
            div({"class": "row"}, h2("Private pulse"), span({"class": "pill lock"}, "ticket")),
            p(f"Updates only if your page ticket authorizes «{TOPIC_PRIVATE}»."),
            p({"class": "big"}, str(n)),
        )


class Controls(Region):
    def render(self, ctx):
        s = _state()
        run = s.get("running", True)
        return div(
            {"class": "card controls"},
            h2("Actions (Intent → Result)"),
            p(
                "Signed caps on buttons (POST /action). Live morphs also fan out "
                "on the open WebSocket so every tab stays in sync."
            ),
            div(
                {"class": "btns"},
                button(
                    {"type": "button", "class": "btn", **ch.control(self.toggle).as_ux_dom()},
                    "Pause feeder" if run else "Resume feeder",
                ),
                button(
                    {"type": "button", "class": "btn primary", **ch.control(self.bump).as_ux_dom()},
                    "Bump gold +10",
                ),
                button(
                    {
                        "type": "button",
                        "class": "btn",
                        **ch.control(self.shout, trust_msg="order filled").as_ux_dom(),
                    },
                    'Shout "filled"',
                ),
                button(
                    {
                        "type": "button",
                        "class": "btn accent",
                        **ch.control(self.pulse_private).as_ux_dom(),
                    },
                    "Private +1",
                ),
            ),
        )

    @Region.action(refresh=["ws.ticker", "ws.status", "ws.tape", "ws.controls"])
    def toggle(self):
        s = dict(_state())
        s["running"] = not s.get("running", True)
        s["last_event"] = "resume" if s["running"] else "pause"
        s["conn_hint"] = "Feeder " + ("running" if s["running"] else "paused") + " via Intent"
        _save(s)
        _push("ws.ticker", "ws.status", "ws.tape", "ws.controls")

    @Region.action(refresh=["ws.ticker", "ws.tape", "ws.status"])
    def bump(self):
        s = dict(_state())
        s["gold"] = round(float(s["gold"]) + 10, 2)
        hist = list(s.get("history_g") or [])
        hist.append(s["gold"])
        s["history_g"] = hist[-16:]
        s["last_event"] = "bump +10"
        s["shouts"] = [
            {"t": datetime.now().strftime("%H:%M:%S"), "msg": "manual bump gold +10"}
        ] + list(s.get("shouts") or [])
        s["shouts"] = s["shouts"][:20]
        _save(s)
        _push("ws.ticker", "ws.tape", "ws.status")

    @Region.action(refresh=["ws.tape", "ws.status"])
    def shout(self, msg: str = "hello"):
        # Store plain text — ux-dom escapes on paint (pre-escape caused &lt; bugs)
        plain = str(msg)[:80]
        s = dict(_state())
        s["shouts"] = [
            {"t": datetime.now().strftime("%H:%M:%S"), "msg": plain}
        ] + list(s.get("shouts") or [])
        s["shouts"] = s["shouts"][:20]
        s["last_event"] = f"shout:{plain}"
        _save(s)
        _push("ws.tape", "ws.status")

    @Region.action(refresh=["ws.private", "ws.status", "ws.controls"])
    def pulse_private(self):
        s = dict(_state())
        s["private_n"] = int(s.get("private_n") or 0) + 1
        s["last_event"] = "private pulse"
        _save(s)
        _push("ws.private", "ws.status")


# ── App / feeder ─────────────────────────────────────────────────────────


async def _feeder() -> None:
    while True:
        try:
            s = dict(_state())
            await asyncio.sleep(1.4)
            # re-read after sleep so pause/toggle is not stale
            s = dict(_state())
            if not s.get("running", True):
                continue
            s["gold"] = round(float(s["gold"]) + random.uniform(-8, 8), 2)
            s["silver"] = round(max(1.0, float(s["silver"]) + random.uniform(-0.4, 0.4)), 2)
            s["ticks"] = int(s.get("ticks") or 0) + 1
            s["last_event"] = f"tick #{s['ticks']}"
            hg = list(s.get("history_g") or [s["gold"]] * 16)
            hs = list(s.get("history_s") or [s["silver"]] * 16)
            hg.append(s["gold"])
            hs.append(s["silver"])
            s["history_g"] = hg[-16:]
            s["history_s"] = hs[-16:]
            if s["ticks"] % 5 == 0:
                s["shouts"] = [
                    {
                        "t": datetime.now().strftime("%H:%M:%S"),
                        "msg": f"auto tick {s['ticks']} gold={_inr(s['gold'])}",
                    }
                ] + list(s.get("shouts") or [])
                s["shouts"] = s["shouts"][:20]
            _save(s)
            bus = get_push_bus()
            bus.publish(TOPIC_TICKER, ch.refresh("ws.ticker"))
            bus.publish(TOPIC_STATUS, ch.refresh("ws.status"))
            if s["ticks"] % 5 == 0:
                bus.publish(TOPIC_TAPE, ch.refresh("ws.tape"))
            if s.get("private_n"):
                bus.publish(TOPIC_PRIVATE, ch.refresh("ws.private"))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("feeder tick failed")
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_feeder())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="uxchannel WebSocket demo", lifespan=lifespan)
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        # Fail-closed for non-public topics so shop.ws.pulse needs a ticket
        # (public.* still open via push_public_prefixes).
        push_require_auth=True,
    ),
)

ticker = Ticker(ch, uid="ws.ticker").mount()
tape = Tape(ch, uid="ws.tape").mount()
status = LinkStatus(ch, uid="ws.status").mount()
private = PrivatePulse(ch, uid="ws.private").mount()
controls = Controls(ch, uid="ws.controls").mount()

CSS = """
:root {
  --bg: #0c1118;
  --card: #141c27;
  --line: #243041;
  --text: #e8eef6;
  --muted: #8b9bb0;
  --gold: #e8b84a;
  --accent: #5b9fd4;
  --ok: #3dbe8c;
  --bad: #e07070;
  --font: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh;
  font-family: var(--font);
  background: radial-gradient(1200px 600px at 10% -10%, #1a2740 0%, var(--bg) 55%);
  color: var(--text);
  line-height: 1.45;
}
.wrap { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }
header { margin-bottom: 1.25rem; }
header h1 { font-size: 1.55rem; font-weight: 650; margin: 0 0 0.35rem; letter-spacing: -0.02em; }
header .lead { color: var(--muted); margin: 0; max-width: 52rem; }
.badge {
  display: inline-block; margin-top: 0.65rem;
  font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--accent); border: 1px solid #2a4a66; background: #132033;
  padding: 0.2rem 0.55rem; border-radius: 999px;
}
.grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1rem;
}
@media (max-width: 820px) { .grid { grid-template-columns: 1fr; } }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1rem 1.1rem 1.1rem;
  box-shadow: 0 8px 28px rgba(0,0,0,.25);
}
.card h2 { font-size: 0.95rem; margin: 0; font-weight: 600; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.75rem; }
.pill {
  font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--muted); border: 1px solid var(--line); padding: 0.15rem 0.45rem; border-radius: 6px;
}
.pill.on { color: var(--ok); border-color: #2a5a45; }
.pill.off { color: var(--bad); border-color: #5a3030; }
.pill.lock { color: #c9a0e8; border-color: #4a3560; }
.prices { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.price { background: #0f1620; border-radius: 10px; padding: 0.65rem 0.7rem; border: 1px solid #1e2a3a; }
.price .lbl { display: block; font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
.price .val { display: block; font-size: 1.25rem; font-weight: 650; margin: 0.2rem 0 0.35rem; font-variant-numeric: tabular-nums; }
.price.gold .val { color: var(--gold); }
.meta { color: var(--muted); font-size: 0.82rem; margin: 0.5rem 0 0; }
.meta.mono, .mono { font-family: var(--mono); font-size: 0.75rem; word-break: break-all; }
.tape-body { max-height: 220px; overflow: auto; display: flex; flex-direction: column; gap: 0.35rem; }
.tape-line { display: flex; gap: 0.65rem; font-size: 0.85rem; padding: 0.35rem 0.4rem; background: #0f1620; border-radius: 6px; }
.tape-line .t { color: var(--muted); font-family: var(--mono); font-size: 0.75rem; min-width: 4.2rem; }
.empty { color: var(--muted); font-size: 0.88rem; }
.big { font-size: 2.2rem; font-weight: 700; margin: 0.4rem 0; color: #c9a0e8; font-variant-numeric: tabular-nums; }
.btns { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.btn {
  appearance: none; border: 1px solid var(--line); background: #1a2433; color: var(--text);
  border-radius: 8px; padding: 0.45rem 0.75rem; font: inherit; font-size: 0.88rem; cursor: pointer;
}
.btn:hover { border-color: #3a4d66; background: #1f2c3f; }
.btn.primary { background: #2a3f5c; border-color: #3d6a9a; }
.btn.accent { background: #2a2240; border-color: #5a4580; color: #e6d4ff; }
.hint {
  margin-top: 1rem; padding: 0.85rem 1rem; border-radius: 10px;
  background: #101820; border: 1px dashed #2a3a4e; color: var(--muted); font-size: 0.85rem;
}
.hint code { color: #b8d4f0; font-family: var(--mono); font-size: 0.8rem; }
.ws-bar {
  display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: center;
  margin: 0.85rem 0 1.1rem; padding: 0.55rem 0.75rem;
  background: #101a28; border: 1px solid #243448; border-radius: 10px; font-size: 0.82rem;
}
.ws-bar .dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--muted); display: inline-block;
}
.ws-bar.live .dot { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.ws-bar .lab { color: var(--muted); }
#ws-log {
  margin-top: 0.75rem; font-family: var(--mono); font-size: 0.72rem; color: var(--muted);
  max-height: 120px; overflow: auto; white-space: pre-wrap;
}
"""


def _page() -> str:
    ticket = ch.sign_ws(TOPIC_PRIVATE, sub="demo-user")
    topics = ",".join(
        [TOPIC_TICKER, TOPIC_TAPE, TOPIC_STATUS, TOPIC_CONTROLS, TOPIC_PRIVATE]
    )
    body_attrs = attr_string(ch.body_attrs(
        ws=True,
        push_topic=topics,
        push_ticket=ticket,
        dev=True,
    ))
    body_inner = div(
        {"class": "wrap"},
        raw("<header>"),
        h1("WebSocket live board"),
        p(
            {"class": "lead"},
            "ux-dom renders the page; uxchannel owns regions, signed actions, "
            "and a single duplex WebSocket for multi-topic live morphs.",
        ),
        span({"class": "badge"}, "examples/ws_live_board · uxchannel 0.1"),
        raw("</header>"),
        div(
            {"class": "ws-bar", "id": "ws-bar"},
            span({"class": "dot", "aria-hidden": "true"}),
            span({"class": "lab"}, "WebSocket:"),
            span({"id": "ws-state"}, "connecting..."),
            button({"type": "button", "class": "btn", "id": "ws-ping"}, "Ping socket"),
        ),
        div(
            {"class": "grid"},
            div(
                raw(ticker.html()),
                raw(controls.html()),
                div(
                    {"class": "hint"},
                    raw(
                        "<strong>Try:</strong> leave the tab open — ticker morphs over WS. "
                        "Use <em>Bump</em> / <em>Shout</em>. "
                        "<em>Private +1</em> needs the page ticket for "
                        f"<code>{html_lib.escape(TOPIC_PRIVATE)}</code>. "
                        "Topics: <code>"
                        + html_lib.escape(topics)
                        + "</code>"
                    ),
                ),
            ),
            div(
                raw(status.html()),
                raw(tape.html()),
                raw(private.html()),
                div({"id": "ws-log", "aria-label": "websocket log"}),
            ),
        ),
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WS Live Board — ux-channel</title>
<style>{CSS}</style>
{demo_scripts(ch, )}
<script>
(function () {{
  function setLive(on, text) {{
    var bar = document.getElementById("ws-bar");
    var st = document.getElementById("ws-state");
    if (bar) bar.classList.toggle("live", !!on);
    if (st) st.textContent = text || (on ? "connected" : "idle");
  }}
  function log(line) {{
    var el = document.getElementById("ws-log");
    if (!el) return;
    var t = new Date().toISOString().slice(11, 19);
    var nl = String.fromCharCode(10);
    var prev = (el.textContent || "").split(nl).slice(0, 8).join(nl);
    el.textContent = "[" + t + "] " + line + nl + prev;
  }}
  document.addEventListener("DOMContentLoaded", function () {{
    if (!window.uidChannel || !uidChannel.subscribeWs) {{
      setLive(false, "client missing subscribeWs");
      return;
    }}
    // Do NOT call subscribeWs again — body data-channel-ws already auto-connects.
    // A second connect closes the first and drops live ticks.
    if (uidChannel.onWsMessage) {{
      uidChannel.onWsMessage(function (msg) {{
        if (!msg || !msg.type) return;
        if (msg.type === "hello") {{
          setLive(true, "hello uid=" + (msg.uid || "?") + " rt=" + (msg.runtime || ""));
          log("hello " + JSON.stringify(msg));
        }} else if (msg.type === "subscribed") {{
          log("subscribed " + msg.topic);
        }} else if (msg.type === "result") {{
          log("result ops=" + ((msg.ops && msg.ops.length) || 0) + " ok=" + msg.ok);
        }} else if (msg.type === "error") {{
          log("error " + msg.code + ": " + msg.message);
        }} else if (msg.type === "ping" || msg.type === "pong") {{
          log(msg.type);
        }}
      }});
    }}
    // Ping uses the auto socket via subscribeWs() return of existing handle
    var pingBtn = document.getElementById("ws-ping");
    if (pingBtn) {{
      pingBtn.addEventListener("click", function () {{
        var ws = uidChannel.getWs && uidChannel.getWs();
        if (ws && ws.readyState === 1) {{
          ws.send(JSON.stringify({{ type: "ping" }}));
          log("ping sent");
        }} else {{
          log("socket not open");
        }}
      }});
    }}
    // connection state from first hello log + optimistic
    setLive(true, "connecting...");
  }});
}})();
</script>
</head>
<body {body_attrs}>
{body_inner}
</body>
</html>"""


@app.get("/")
def index():
    return HTMLResponse(_page())


@app.get("/health")
def health():
    return {"ok": True, "demo": "ws_live_board"}
