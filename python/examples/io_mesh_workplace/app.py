"""
I/O mesh workplace — Workplace façade + phases A1–A3.

  * Workplace binds room claim · I/O gate · claim-aware agents
  * scan ≡ button ≡ wp.dispatch
  * party TTL · lab Quantity budget · I/O audit

  PYTHONPATH=src uvicorn examples.io_mesh_workplace.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig, attach_audit, state
from ux_channel.paint.demo import demo_button, script_tags
from ux_channel.io_adapters import LabDutAdapter, LightsAdapter, ScannerAdapter
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import workplace

SECRET = "io-mesh-workplace-demo-secret-key-32b!"

app = FastAPI(title="uxchannel I/O mesh workplace")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=False,
        audit=True,
    ),
)
st = state(ch)
audit = attach_audit(ch)

scanner = ScannerAdapter()
lights = LightsAdapter()
lab = LabDutAdapter(dut_id="dut-42")

# Default desk: POS claim (rebind for party/lab actions as needed)
wp = workplace(
    ch,
    ticket={
        "room": "pos-desk",
        "peer_id": "clerk-1",
        "scopes": ["scan", "pos", "add", "cart", "clear"],
    },
).allow(scanner, lights, lab)

CART: dict[str, int] = {}
NOTICES: list[str] = []


def _notice(msg: str) -> None:
    NOTICES.append(msg)
    if len(NOTICES) > 40:
        del NOTICES[:-40]


def _wp_party():
    return workplace(
        ch,
        ticket={
            "room": "party",
            "peer_id": "guest-phone",
            "scopes": ["lights"],
            "exp": time.time() + 3600,
        },
        attach=False,
    ).allow(lights)


def _wp_lab():
    return workplace(
        ch,
        ticket={
            "room": "lab-cell",
            "peer_id": "tech-9",
            "scopes": ["lab", "lab.flash", "view"],
        },
        attach=False,
    ).allow(lab)


@ch.on
def add_line(sku: str = "") -> Any:
    code = (sku or "").strip()
    if not code:
        return ch.fail.validation("sku required")
    CART[code] = CART.get(code, 0) + 1
    _notice(f"added {code} (qty {CART[code]})")
    return ch.done(notice=f"added {code}", refresh=["cart", "status"])


@ch.on
def clear_cart() -> Any:
    CART.clear()
    _notice("cart cleared")
    return ch.done(notice="cart cleared", refresh=["cart", "status"])


@ch.on
def lights_scene(scene: str = "party") -> Any:
    w = _wp_party()
    try:
        out = w.run_io("home.lights", "scene", [scene])
    except Exception as exc:
        return ch.fail.validation(str(exc))
    _notice(f"lights {out}")
    return ch.done(notice=f"lights {out.get('scene')}", refresh=["party", "status"])


@ch.on
def lights_off() -> Any:
    w = _wp_party()
    try:
        w.run_io("home.lights", "scene", ["off"])
    except Exception as exc:
        return ch.fail.validation(str(exc))
    return ch.done(notice="lights off", refresh=["party", "status"])


@ch.on
def lab_flash() -> Any:
    w = _wp_lab()
    q = Quantity.from_store(
        1, "count", source="lab.policy.flash_budget", revision=lab.flash_count + 1
    )
    try:
        out = w.run_io("lab.dut", "flash", quantity=q)
    except Exception as exc:
        return ch.fail.validation(str(exc))
    _notice(f"lab flash {out}")
    return ch.done(notice=f"flashed {out.get('dut_id')}", refresh=["lab", "status"])


@ch.on
def scanner_scan(sku: str = "SKU-100") -> Any:
    payload = scanner.inject(sku)
    args = wp.check_event(
        scanner.name, "scanned", payload, method_for_keys="read"
    )
    return add_line(sku=str(args.get("sku") or payload.get("sku") or ""))


@ch.region("status")
def status_region(ctx: Any) -> str:
    last = NOTICES[-1] if NOTICES else "—"
    snap = wp.snapshot()
    return (
        f'<div class="card" data-channel-id="status">'
        f"<h2>Workplace · I/O mesh</h2>"
        f"<p class='muted'>room=<code>{snap['room']}</code> peer=<code>{snap['peer_id']}</code> "
        f"scopes={snap['scopes']}</p>"
        f"<p><b>last:</b> {last}</p></div>"
    )


@ch.region("cart")
def cart_region(ctx: Any) -> str:
    if not CART:
        body = "<p class='muted'>cart empty — scan or add</p>"
    else:
        rows = "".join(f"<li><code>{k}</code> × {v}</li>" for k, v in CART.items())
        body = f"<ul>{rows}</ul>"
    return f'<div class="card" data-channel-id="cart"><h3>Cart</h3>{body}</div>'


@ch.region("party")
def party_region(ctx: Any) -> str:
    w = _wp_party()
    st_ = w.run_io("home.lights", "status")
    return (
        f'<div class="card" data-channel-id="party"><h3>Party room</h3>'
        f"<p>on={st_['on']} scene=<b>{st_['scene']}</b></p>"
        f"<p class='muted'>Workplace claim scopes: lights only</p></div>"
    )


@ch.region("lab")
def lab_region(ctx: Any) -> str:
    w = _wp_lab()
    info = w.run_io("lab.dut", "id")
    return (
        f'<div class="card" data-channel-id="lab"><h3>Lab DUT</h3>'
        f"<p>id=<code>{info['dut_id']}</code> flashes=<b>{info['flashes']}</b></p>"
        f"<p class='muted'>wp.run_io + Quantity budget</p></div>"
    )


@app.get("/api/io-audit")
def api_io_audit() -> JSONResponse:
    return JSONResponse(
        {
            "io": wp.export_io_audit(),
            "workplace": wp.snapshot(),
        }
    )


@app.get("/api/situation")
def api_situation() -> JSONResponse:
    wp.put_facts(cart=dict(CART))
    return JSONResponse(wp.situation())


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    css = """
    body{font-family:system-ui,sans-serif;margin:0;background:#0f1419;color:#e7ecf3}
    main{max-width:960px;margin:0 auto;padding:1.25rem;display:grid;gap:1rem}
    .card{background:#1a2332;border-radius:12px;padding:1rem 1.25rem;border:1px solid #2a3548}
    .row{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
    button{background:#3b82f6;color:#fff;border:0;border-radius:8px;padding:.45rem .85rem;cursor:pointer}
    h2,h3{margin:.2rem 0 .6rem}
    .muted{opacity:.75;font-size:.9rem}
    code{background:#0b1220;padding:.1rem .35rem;border-radius:4px}
    ul{margin:.3rem 0;padding-left:1.2rem}
    a{color:#93c5fd}
    """
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Workplace · I/O mesh</title>
{script_tags(ch)}
<style>{css}</style>
</head><body {ch.body_attr_string()}>
<main>
  {status_region(None)}
  {cart_region(None)}
  <div class="card">
    <h3>A1 · POS — Workplace.dispatch ≡ button ≡ scan</h3>
    <div class="row">
      {demo_button(ch, "Add SKU-100", add_line, trust_sku="SKU-100")}
      {demo_button(ch, "Add SKU-200", add_line, trust_sku="SKU-200")}
      {demo_button(ch, "Scanner inject", scanner_scan, trust_sku="SKU-100")}
      {demo_button(ch, "Clear cart", clear_cart)}
    </div>
  </div>
  {party_region(None)}
  <div class="card">
    <h3>A2 · Party Workplace (lights)</h3>
    <div class="row">
      {demo_button(ch, "Scene party", lights_scene, trust_scene="party")}
      {demo_button(ch, "Scene dim", lights_scene, trust_scene="dim")}
      {demo_button(ch, "Lights off", lights_off)}
    </div>
  </div>
  {lab_region(None)}
  <div class="card">
    <h3>A3 · Lab Workplace (budgeted flash)</h3>
    <div class="row">
      {demo_button(ch, "Flash DUT", lab_flash)}
    </div>
  </div>
  <div class="card muted">
    <p><a href="/api/situation">/api/situation</a> ·
    <a href="/api/io-audit">/api/io-audit</a> · docs/workplace/WORKPLACE.md</p>
  </div>
</main>
</body></html>"""
    return HTMLResponse(html)
