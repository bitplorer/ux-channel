"""
Workplace starter kit — copy this app for a real deploy.

Includes:
  * Channel boot (prod-shaped knobs via env)
  * issue_mesh_membership / Workplace
  * Quantity
  * Intent outbox (offline queue + drain)
  * Optional MCP mount for agent vertical
  * Audit export

  PYTHONPATH=src uvicorn examples.workplace_kit.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Mapping, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig, attach_audit, state
from ux_channel.agents import AgentPolicy, agent_tool
from ux_channel.render.kit import script_tags
from ux_channel.io_adapters import ScannerAdapter
from ux_channel.transport.outbox import (
    MemoryIntentOutbox,
    OutboxItem,
    attach_outbox,
    drain_outbox,
)
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import (
    issue_mesh_membership,
    revoke_mesh_membership,
    workplace_from_membership,
)

SECRET = os.environ.get("UX_CHANNEL_SECRET", "workplace-kit-dev-secret-key-32b!!")
ENV = os.environ.get("UX_CHANNEL_ENV", "development").lower()
REDIS_URL = os.environ.get("REDIS_URL") or None
AGENT_TOKEN = os.environ.get("UX_CHANNEL_AGENT_TOKEN", "kit-agent-token")
ORIGIN = os.environ.get("UX_CHANNEL_ORIGIN", "http://127.0.0.1:8080")

app = FastAPI(title="Workplace Kit")

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
        mount_agent_mcp=True,
        agent_token=AGENT_TOKEN,
    )
else:
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        audit=True,
        redis_url=REDIS_URL,
        mount_agent_mcp=True,
        agent_token=AGENT_TOKEN,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
    )

ch = Channel.boot(app, config=cfg, redis_url=REDIS_URL)
st = state(ch)
audit = attach_audit(ch)
outbox = attach_outbox(ch, MemoryIntentOutbox())
scanner = ScannerAdapter()

PRICES = {"SKU-100": Decimal("9.50"), "SKU-200": Decimal("14.00")}
CART: dict[str, int] = {}
RUNTIME: dict[str, Any] = {}

# Scopes named so claim prefix rules match action names (add_*, pay_*, queue_*, drain_*)
KIT_SCOPES = [
    "pos",
    "add",
    "scan",
    "pay",
    "clear",
    "cart",
    "queue",
    "drain",
    "outbox",
]


def _membership(sub: str = "clerk-1"):
    return issue_mesh_membership(
        ch,
        "kit-desk",
        sub=sub,
        scopes=KIT_SCOPES,
        max_age=900,
    )


RUNTIME["mem"] = _membership()
RUNTIME["wp"] = workplace_from_membership(ch, RUNTIME["mem"]).allow(scanner)


def wp():
    return RUNTIME["wp"]


def _hdr(h: Optional[str]) -> None:
    if cfg.require_channel_header and h != "1":
        raise HTTPException(403, "X-Channel required")


def load_price(sku: str) -> Quantity:
    return Quantity.from_store(
        PRICES[sku], "USD", source=f"db.catalog.{sku}.price", revision=1
    )


@ch.on
@agent_tool("Add line to cart", tags=("pos", "cart"))
def add_line(sku: str = "") -> Any:
    code = (sku or "").strip()
    if code not in PRICES:
        return ch.fail.validation(f"unknown {code}")
    CART[code] = CART.get(code, 0) + 1
    return ch.done(notice=f"added {code}", refresh=["cart", "desk"])


@ch.on
@agent_tool("Pay cart totals from store prices", dangerous=True, tags=("pos", "pay"))
def pay_cart() -> Any:
    if not CART:
        return ch.fail.validation("empty")
    total = sum(load_price(s).magnitude * n for s, n in CART.items())
    q = Quantity.from_store(total, "USD", source="db.cart.total", revision=1)
    CART.clear()
    return ch.done(notice=f"PAID {q.magnitude}", refresh=["cart", "desk"])


@ch.on
@agent_tool("Enqueue action for offline drain", tags=("outbox",))
def queue_add(sku: str = "SKU-100") -> Any:
    """Simulate offline: put Intent in outbox instead of immediate apply."""
    item = outbox.enqueue(
        "add_line",
        {"sku": sku},
        room=wp().claim.room,
        peer_id=wp().claim.peer_id,
        scopes=tuple(wp().claim.scopes),
        idempotency_key=f"add:{sku}:{len(CART)}",
    )
    return ch.done(notice=f"queued {item.id}", refresh=["desk"])


@ch.on
@agent_tool("Drain outbox through Workplace", tags=("outbox",))
def drain_now() -> Any:
    def _dispatch(action: str, args: Mapping[str, Any], item: OutboxItem):
        return wp().dispatch(action, dict(args))

    stats = drain_outbox(outbox, _dispatch, batch=50)
    return ch.done(notice=str(stats), refresh=["cart", "desk"])


@ch.on
def scanner_scan(sku: str = "SKU-100") -> Any:
    payload = scanner.inject(sku)
    args = wp().check_event(
        scanner.name, "scanned", payload, method_for_keys="read"
    )
    return add_line(sku=str(args.get("sku") or sku))


@ch.region("desk")
def desk_region(ctx: Any) -> str:
    snap = wp().snapshot()
    return (
        f'<div class="card" data-channel-id="desk"><h2>Workplace Kit</h2>'
        f"<p class='muted'>env={ENV} pending_outbox={outbox.pending_count()}</p>"
        f"<p>room=<code>{snap['room']}</code> peer=<code>{snap['peer_id']}</code></p>"
        f"</div>"
    )


@ch.region("cart")
def cart_region(ctx: Any) -> str:
    body = (
        "<p class='muted'>empty</p>"
        if not CART
        else "<ul>"
        + "".join(f"<li>{k} × {v}</li>" for k, v in CART.items())
        + "</ul>"
    )
    return f'<div class="card" data-channel-id="cart"><h3>Cart</h3>{body}</div>'


app.state.uid_agent_policy = AgentPolicy.production(
    allow=["add_line", "pay_cart", "queue_add", "drain_now"],
    max_calls_per_session=200,
)


@app.post("/api/membership")
async def api_membership(
    request: Request,
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    try:
        body = await request.json()
    except Exception:
        body = {}
    sub = str((body or {}).get("sub") or "clerk-1")[:64]
    RUNTIME["mem"] = _membership(sub)
    RUNTIME["wp"] = workplace_from_membership(ch, RUNTIME["mem"]).allow(scanner)
    return JSONResponse(RUNTIME["mem"].to_dict())


@app.post("/api/logout")
def api_logout(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    revoke_mesh_membership(RUNTIME["mem"], channel=ch)
    return JSONResponse({"revoked": True})


@app.get("/api/outbox")
def api_outbox(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    return JSONResponse(
        {
            "pending": outbox.pending_count(),
            "items": [i.to_dict() for i in outbox.list(limit=50)],
        }
    )


@app.get("/api/audit")
def api_audit(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    out: dict[str, Any] = {"io": wp().export_io_audit(), "workplace": wp().snapshot()}
    if hasattr(audit, "export"):
        out["channel"] = audit.export()
    return JSONResponse(out)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    w = wp()
    buttons = [
        ("Add SKU-100", w.control(add_line, trust_sku="SKU-100")),
        ("Scan SKU-200", w.control(scanner_scan, trust_sku="SKU-200")),
        ("Queue add (offline)", w.control(queue_add, trust_sku="SKU-100")),
        ("Drain outbox", w.control(drain_now)),
        ("Pay", w.control(pay_cart)),
    ]

    def btn(label: str, ctrl) -> str:
        return f"<button type='button' {ctrl}>{label}</button>"

    row = "".join(btn(a, b) for a, b in buttons)
    css = """
    body{font-family:system-ui,sans-serif;margin:0;background:#0b1220;color:#e8eef8}
    main{max-width:760px;margin:0 auto;padding:1.2rem;display:grid;gap:1rem}
    .card{background:#151d2e;border:1px solid #2a3548;border-radius:12px;padding:1rem}
    button{background:#4f46e5;color:#fff;border:0;border-radius:8px;padding:.45rem .8rem;margin:.2rem;cursor:pointer}
    .muted{opacity:.75;font-size:.9rem} code{background:#0a101c;padding:.1rem .3rem;border-radius:4px}
    a{color:#a5b4fc}
    """
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Workplace Kit</title>{script_tags(ch)}<style>{css}</style>
</head><body {ch.body_attr_string()}>
<main>
{desk_region(None)}
{cart_region(None)}
<div class="card"><h3>Kit controls</h3><div>{row}</div>
<p class="muted">MCP: <code>GET /ux-channel/mcp/tools</code> Bearer {AGENT_TOKEN} ·
<a href="/api/outbox">outbox</a> · <a href="/api/audit">audit</a></p>
<p class="muted">Copy this example for deploy. See docs/workplace/WORKPLACE_KIT.md</p>
</div>
</main></body></html>"""
    )
