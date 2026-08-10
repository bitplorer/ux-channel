"""
MCP verticals on Workplace — POS + Lab tools for agents.

Same Intent door as UI; scoped by workplace membership.

  UX_CHANNEL_AGENT_TOKEN=dev-token \\
  PYTHONPATH=src uvicorn examples.mcp_verticals.app:app --host 0.0.0.0 --port 8080

  curl -H "Authorization: Bearer dev-token" http://127.0.0.1:8080/ux-channel/mcp/tools
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig, attach_audit
from ux_channel.agents import AgentPolicy, agent_tool
from ux_channel.io_adapters import LabDutAdapter, ScannerAdapter
from ux_channel.transport.outbox import MemoryIntentOutbox, attach_outbox, drain_outbox
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import issue_mesh_membership, workplace_from_membership
from ux_channel.mcp import register_builtin_verticals
from ux_channel.transport.outbox import get_outbox

SECRET = os.environ.get("UX_CHANNEL_SECRET", "mcp-verticals-secret-key-32bytes!!")
AGENT_TOKEN = os.environ.get("UX_CHANNEL_AGENT_TOKEN", "dev-token")

app = FastAPI(title="MCP Verticals")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=False,
        require_channel_header=False,
        mount_agent_mcp=True,
        agent_token=AGENT_TOKEN,
        agent_confirmation_secret=SECRET,
        mcp_verticals=("pos", "lab"),
        mcp_resource_regions=("cart",),
        mcp_session_ttl_s=900,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        audit=True,
    ),
)
attach_audit(ch)
register_builtin_verticals(replace=True)
outbox = attach_outbox(ch, MemoryIntentOutbox())
app.state.ux_channel = ch

scanner = ScannerAdapter()
lab = LabDutAdapter(dut_id="dut-mcp")
CART: dict[str, int] = {}
PRICES = {"SKU-100": Decimal("9.50"), "SKU-200": Decimal("14.00")}

# Two logical verticals share one process; separate memberships in real deploy
POS = workplace_from_membership(
    ch,
    issue_mesh_membership(
        ch, "pos", sub="mcp-pos", scopes=["pos", "add", "scan", "pay", "outbox"]
    ),
    attach=False,
).allow(scanner)

LAB = workplace_from_membership(
    ch,
    issue_mesh_membership(
        ch, "lab", sub="mcp-lab", scopes=["lab", "lab.flash", "view"]
    ),
    attach=False,
).allow(lab)


# ── POS vertical tools ────────────────────────────────────────────────────


@ch.on
@agent_tool("POS: add SKU to cart", tags=("vertical:pos", "cart"))
def pos_add_line(sku: str = "SKU-100") -> Any:
    if sku not in PRICES:
        return ch.fail.validation("unknown sku")
    # enforce POS claim
    POS.ensure_action("pos_add_line")
    CART[sku] = CART.get(sku, 0) + 1
    return ch.done(notice=f"cart {CART}")


@ch.on
@agent_tool("POS: pay cart", dangerous=True, tags=("vertical:pos", "pay"))
def pos_pay() -> Any:
    POS.ensure_action("pos_pay")
    if not CART:
        return ch.fail.validation("empty cart")
    total = sum(PRICES[s] * n for s, n in CART.items())
    q = Quantity.from_store(total, "USD", source="db.cart.total", revision=1)
    CART.clear()
    return ch.done(notice=f"paid {q.magnitude} {q.unit}")


@ch.on
@agent_tool("POS: queue add when offline", tags=("vertical:pos", "outbox"))
def pos_queue_add(sku: str = "SKU-100") -> Any:
    POS.ensure_action("pos_queue_add")
    item = outbox.enqueue(
        "pos_add_line",
        {"sku": sku},
        room=POS.claim.room,
        peer_id=POS.claim.peer_id,
        scopes=tuple(POS.claim.scopes),
    )
    return ch.done(notice=f"queued {item.id}")


@ch.on
@agent_tool("POS: drain outbox", dangerous=True, tags=("vertical:pos", "outbox"))
def pos_drain() -> Any:
    POS.ensure_action("pos_drain")

    def _d(action, args, item):
        return POS.dispatch(action, dict(args))

    return ch.done(notice=str(drain_outbox(outbox, _d)))


# ── Lab vertical tools ────────────────────────────────────────────────────


@ch.on
@agent_tool("Lab: read DUT id", read_only=True, tags=("vertical:lab",))
def lab_read() -> Any:
    LAB.ensure_action("lab_read")
    info = LAB.run_io("lab.dut", "id")
    return ch.done(notice=str(info))


@ch.on
@agent_tool("Lab: flash DUT under budget", dangerous=True, tags=("vertical:lab",))
def lab_flash() -> Any:
    LAB.ensure_action("lab_flash")
    q = Quantity.from_store(
        1, "count", source="lab.policy.flash", revision=lab.flash_count + 1
    )
    out = LAB.run_io("lab.dut", "flash", quantity=q)
    return ch.done(notice=str(out))


app.state.uid_agent_policy = AgentPolicy.production(
    allow=[
        "pos_add_line",
        "pos_pay",
        "pos_queue_add",
        "pos_drain",
        "lab_read",
        "lab_flash",
    ],
    confirm=["pos_pay", "pos_drain", "lab_flash"],
    max_calls_per_session=300,
)


@app.get("/api/verticals")
def api_verticals() -> JSONResponse:
    return JSONResponse(
        {
            "pos": POS.snapshot(),
            "lab": LAB.snapshot(),
            "cart": dict(CART),
            "outbox_pending": outbox.pending_count(),
        }
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html><body style="font-family:system-ui;padding:1.5rem">
<h1>MCP Verticals</h1>
<p>POS + Lab tools on Workplace + outbox.</p>
<ul>
<li><code>GET /ux-channel/mcp/tools</code> Authorization: Bearer {AGENT_TOKEN}</li>
<li><code>GET /api/verticals</code></li>
</ul>
<p>See docs/agents/MCP_VERTICALS.md</p>
</body></html>"""
    )
