"""
Hardened POS workplace — production-shaped vertical.

* require_cap + CSRF channel header + same-origin when configured
* issue_mesh_membership (RTC + workplace tickets)
* claim-aware wp.control / dispatch / scanner
* Quantity.from_store only
* Audit export endpoints
* Optional REDIS_URL for durable stores

  PYTHONPATH=src uvicorn examples.workplace_pos.app:app --host 0.0.0.0 --port 8080
  REDIS_URL=redis://… UX_CHANNEL_ENV=production …
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig, attach_audit, state
from ux_channel.demo import script_tags
from ux_channel.io_adapters import ScannerAdapter
from ux_channel.quantity import Quantity
from ux_channel.workplace import (
    MeshMembership,
    issue_mesh_membership,
    workplace_from_membership,
)

SECRET = os.environ.get(
    "UX_CHANNEL_SECRET", "workplace-pos-prod-shaped-secret-key-32b!"
)
ENV = os.environ.get("UX_CHANNEL_ENV", "development").lower()
REDIS_URL = os.environ.get("REDIS_URL") or None
ORIGIN = os.environ.get("UX_CHANNEL_ORIGIN", "http://127.0.0.1:8080")

app = FastAPI(title="Workplace POS (prod-shaped)")

if ENV == "production":
    cfg = ChannelConfig.production(
        SECRET,
        allow_memory_stores=not bool(REDIS_URL),
        require_cap=True,
        require_channel_header=True,
        enforce_same_origin=True,
        allowed_origins=(ORIGIN,),
        redis_url=REDIS_URL,
        audit=True,
        rate_limit_per_minute=int(os.environ.get("UID_RATE_LIMIT", "600") or 600),
    )
else:
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        enforce_same_origin=False,
        audit=True,
        redis_url=REDIS_URL,
    )

ch = Channel.boot(app, config=cfg, redis_url=REDIS_URL)
st = state(ch)
audit_bundle = attach_audit(ch)
scanner = ScannerAdapter()

PRICES = {
    "SKU-100": Decimal("9.50"),
    "SKU-200": Decimal("14.00"),
    "SKU-300": Decimal("4.25"),
}
CART: dict[str, int] = {}
PAID: list[dict[str, Any]] = []

# Runtime bag so rebind does not fight Python global rules
RUNTIME: dict[str, Any] = {}


def _mint_membership(sub: str = "clerk-1") -> MeshMembership:
    return issue_mesh_membership(
        ch,
        "pos-desk",
        sub=sub,
        scopes=["pos", "add", "scan", "pay", "clear", "cart"],
        trust={"station": "front"},
        max_age=600,
    )


RUNTIME["membership"] = _mint_membership(
    os.environ.get("UID_POS_CLERK", "clerk-1")
)
RUNTIME["wp"] = workplace_from_membership(ch, RUNTIME["membership"]).allow(scanner)


def wp():
    return RUNTIME["wp"]


def load_price(sku: str) -> Quantity:
    if sku not in PRICES:
        raise KeyError(sku)
    return Quantity.from_store(
        PRICES[sku],
        "USD",
        source=f"db.catalog.{sku}.price",
        revision=1,
    )


def _check_channel_header(x_ux_channel: Optional[str]) -> None:
    if cfg.require_channel_header and x_ux_channel != "1":
        raise HTTPException(status_code=403, detail="X-Channel required")


@ch.on
def add_line(sku: str = "") -> Any:
    code = (sku or "").strip()
    if code not in PRICES:
        return ch.fail.validation(f"unknown sku {code!r}")
    CART[code] = CART.get(code, 0) + 1
    return ch.done(notice=f"added {code}", refresh=["cart", "desk"])


@ch.on
def clear_cart() -> Any:
    CART.clear()
    return ch.done(notice="cleared", refresh=["cart", "desk"])


@ch.on
def pay_cart() -> Any:
    if not CART:
        return ch.fail.validation("cart empty")
    total = Decimal("0")
    lines = []
    for sku, n in CART.items():
        q = load_price(sku)
        total += q.magnitude * n
        lines.append(
            {
                "sku": sku,
                "n": n,
                "unit": str(q.magnitude),
                "source": q.provenance.source,
            }
        )
    total_q = Quantity.from_store(
        total, "USD", source="db.cart.total", revision=len(PAID) + 1
    )
    PAID.append({"total": str(total_q.magnitude), "lines": lines})
    CART.clear()
    return ch.done(
        notice=f"PAID {total_q.magnitude} {total_q.unit}",
        refresh=["cart", "desk"],
    )


@ch.on
def scanner_scan(sku: str = "SKU-100") -> Any:
    payload = scanner.inject(sku)
    args = wp().check_event(
        scanner.name, "scanned", payload, method_for_keys="read"
    )
    return add_line(sku=str(args.get("sku") or payload.get("sku") or ""))


@ch.region("desk")
def desk_region(ctx: Any) -> str:
    snap = wp().snapshot()
    return (
        f'<div class="card" data-channel-id="desk">'
        f"<h2>POS Workplace (prod-shaped)</h2>"
        f"<p class='muted'>env={ENV} redis={'on' if REDIS_URL else 'off'} "
        f"require_cap={cfg.require_cap}</p>"
        f"<p>room=<code>{snap['room']}</code> peer=<code>{snap['peer_id']}</code></p>"
        f"<p>scopes=<code>{snap['scopes']}</code></p></div>"
    )


@ch.region("cart")
def cart_region(ctx: Any) -> str:
    if not CART:
        body = "<p class='muted'>empty</p>"
    else:
        rows = []
        for sku, n in CART.items():
            q = load_price(sku)
            rows.append(f"<li><code>{sku}</code> × {n} @ {q.magnitude} {q.unit}</li>")
        body = "<ul>" + "".join(rows) + "</ul>"
    last = PAID[-1]["total"] if PAID else "—"
    return (
        f'<div class="card" data-channel-id="cart"><h3>Cart</h3>{body}'
        f"<p class='muted'>last paid: {last} USD</p></div>"
    )


@app.post("/api/membership")
async def api_membership(
    request: Request,
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    """Re-issue mesh membership (server scopes only)."""
    _check_channel_header(x_ux_channel)
    try:
        body = await request.json()
    except Exception:
        body = {}
    sub = str((body or {}).get("sub") or RUNTIME["membership"].sub)[:64]
    mem = _mint_membership(sub)
    RUNTIME["membership"] = mem
    RUNTIME["wp"] = workplace_from_membership(ch, mem).allow(scanner)
    return JSONResponse(mem.to_dict() | {"workplace": RUNTIME["wp"].snapshot()})


@app.get("/api/situation")
def api_situation(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _check_channel_header(x_ux_channel)
    return JSONResponse(
        wp().put_facts(cart=dict(CART), paid_n=len(PAID)).situation()
    )


@app.get("/api/audit")
def api_audit(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    """Support export: intent/forensics bundle + I/O audit."""
    _check_channel_header(x_ux_channel)
    out: dict[str, Any] = {
        "io": wp().export_io_audit(),
        "workplace": wp().snapshot(),
        "membership": RUNTIME["membership"].to_dict(),
    }
    if hasattr(audit_bundle, "export"):
        out["channel"] = audit_bundle.export()
    elif hasattr(audit_bundle, "log"):
        out["intents"] = [e.to_dict() for e in audit_bundle.log.since(0)]
    return JSONResponse(out)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    w = wp()
    btn_add = w.control(add_line, trust_sku="SKU-100")
    btn_scan = w.control(scanner_scan, trust_sku="SKU-200")
    btn_pay = w.control(pay_cart)
    btn_clear = w.control(clear_cart)

    def btn(label: str, ctrl) -> str:
        # str(ControlAttrs) HTML-escapes data-channel-args JSON — never join as_dict raw
        return f"<button type='button' {ctrl}>{label}</button>"

    css = """
    body{font-family:system-ui,sans-serif;margin:0;background:#0b1220;color:#e8eef8}
    main{max-width:720px;margin:0 auto;padding:1.25rem;display:grid;gap:1rem}
    .card{background:#151d2e;border:1px solid #2a3548;border-radius:12px;padding:1rem 1.2rem}
    .row{display:flex;flex-wrap:wrap;gap:.5rem}
    button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:.5rem .9rem;cursor:pointer}
    .muted{opacity:.75;font-size:.9rem} code{background:#0a101c;padding:.1rem .35rem;border-radius:4px}
    a{color:#93c5fd}
    """
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Workplace POS</title>
{script_tags(ch)}
<style>{css}</style>
<script>
window.__UX_CHANNEL_HEADERS = Object.assign(window.__UX_CHANNEL_HEADERS||{{}}, {{"X-Channel":"1"}});
</script>
</head><body {ch.body_attr_string()}>
<main>
  {desk_region(None)}
  {cart_region(None)}
  <div class="card">
    <h3>Three surfaces · one ceiling</h3>
    <div class="row">
      {btn("Add SKU-100 (button)", btn_add)}
      {btn("Scan SKU-200 (adapter→action)", btn_scan)}
      {btn("Pay (Quantity)", btn_pay)}
      {btn("Clear", btn_clear)}
    </div>
    <p class="muted">Agent: <code>wp.dispatch</code> ·
    membership: <code>POST /api/membership</code> ·
    <a href="/api/audit">/api/audit</a> (header X-Channel: 1)</p>
  </div>
</main>
</body></html>"""
    return HTMLResponse(html)
