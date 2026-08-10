"""
Payment app — human controls + multiple agents, same Intent plane.

  PYTHONPATH=src python examples/payment_agents/run_demo.py
  uvicorn examples.payment_agents.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, ChannelConfig, agents, state
from ux_channel.paint.demo import attr_string, demo_button, script_tags
from ux_channel.foundations.quantity import Quantity, QuantityError

SECRET = "payment-agents-demo-secret-key-32b!!"

app = FastAPI(title="uxchannel payment agents")
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
ag = agents(ch)


# ── Durable "DB" (in-process stand-in) ───────────────────────────────────

@dataclass
class Order:
    id: str
    user_id: str
    amount: Decimal
    currency: str = "USD"
    status: str = "open"  # open | paid | refunded
    revision: int = 1


ORDERS: dict[str, Order] = {
    "ord_1001": Order("ord_1001", "user_alice", Decimal("42.00")),
    "ord_1002": Order("ord_1002", "user_bob", Decimal("15.50")),
}


def load_payable(order_id: str) -> Quantity:
    o = ORDERS[order_id]
    return Quantity.from_store(
        o.amount,
        o.currency,
        source=f"db.order.{order_id}.amount",
        revision=o.revision,
    )


# session chrome only (ids / steps — never durable authority quantities)
wizard = st.session("pay_step", "review")
last_notice = st.session("last_notice", "")


@st.region("status")
def status_view(ctx):
    step = wizard()
    note = last_notice() or "—"
    open_n = sum(1 for o in ORDERS.values() if o.status == "open")
    paid_n = sum(1 for o in ORDERS.values() if o.status == "paid")
    return (
        f'<div class="card" data-channel-id="status">'
        f"<h2>Payment desk</h2>"
        f"<p class='muted'>step: <b>{step}</b> · open {open_n} · paid {paid_n}</p>"
        f"<p>{note}</p></div>"
    )


@st.region("orders")
def orders_view(ctx):
    rows = []
    for o in ORDERS.values():
        m = load_payable(o.id)
        rows.append(
            f"<li><code>{o.id}</code> {o.user_id} "
            f"<b>{m.magnitude} {m.unit}</b> "
            f"<span class='pill'>{o.status}</span></li>"
        )
    return (
        f'<ul class="card" data-channel-id="orders">'
        + "".join(rows)
        + "</ul>"
    )


# ── Actions (human button ≡ agent tool) ──────────────────────────────────

@st.action
def select_order(order_id: str = "ord_1001"):
    """Select an order to pay (chrome only — stores id)."""
    if order_id not in ORDERS:
        return ch.fail.validation(f"unknown order {order_id}")
    st.session("selected_order", "").set(order_id)
    wizard.set("confirm")
    last_notice.set(f"Selected {order_id}")
    return st.done(refresh=["status", "orders"], notice=f"Selected {order_id}")


@st.action
def pay_order(order_id: str = ""):
    """
    Charge order from durable amount (never trust client amount).
    """
    oid = order_id or st.session("selected_order", "").peek() or ""
    if not oid or oid not in ORDERS:
        return ch.fail.validation("select an order first")
    # refuse client-supplied durable authority
    st.db.guard({"order_id": oid})  # strips risky keys if any
    order = ORDERS[oid]
    if order.status != "open":
        return ch.fail.validation(f"order is {order.status}")
    money = load_payable(oid)
    st.db.require(amount=float(money.magnitude))  # demo: require loaded fields
    order.status = "paid"
    order.revision += 1
    wizard.set("done")
    last_notice.set(f"PAID {money.magnitude} {money.unit} · {oid}")
    return st.done(
        refresh=["status", "orders"],
        notice=f"Paid {money.magnitude} {money.unit}",
    )


@st.action
def refund_order(order_id: str = ""):
    """Refund a paid order (restricted agents only)."""
    oid = order_id or st.session("selected_order", "").peek() or ""
    if not oid or oid not in ORDERS:
        return ch.fail.validation("need order_id")
    order = ORDERS[oid]
    if order.status != "paid":
        return ch.fail.validation("only paid orders refund")
    money = load_payable(oid)
    order.status = "refunded"
    order.revision += 1
    last_notice.set(f"REFUNDED {money.magnitude} · {oid}")
    wizard.set("review")
    return st.done(refresh=["status", "orders"], notice=f"Refunded {oid}")


@st.action
def reset_demo():
    """Reset demo orders to open."""
    for o in ORDERS.values():
        o.status = "open"
        o.revision = 1
    wizard.set("review")
    last_notice.set("Demo reset")
    st.session("selected_order", "").set("")
    return st.done(refresh=["status", "orders"], notice="Reset")


@app.get("/", response_class=HTMLResponse)
def index():
    rt = ch.runtime()
    body = ch.body_attrs()
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Payment agents</title>
{script_tags(rt)}
<style>
  :root {{ color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
  body {{ margin:0; background:#0b1220; color:#e2e8f0; }}
  main {{ max-width:40rem; margin:0 auto; padding:2rem 1rem; }}
  .card {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1rem 1.25rem; margin:1rem 0; }}
  .muted {{ color:#94a3b8; }}
  .pill {{ background:#1e293b; padding:.15rem .5rem; border-radius:999px; font-size:.85rem; }}
  .row {{ display:flex; flex-wrap:wrap; gap:.5rem; margin:1rem 0; }}
  button {{ border:0; border-radius:8px; padding:.55rem 1rem; font-weight:600; cursor:pointer;
    background:linear-gradient(135deg,#6366f1,#06b6d4); color:#fff; }}
  code {{ color:#a5b4fc; }}
  ul {{ list-style:none; padding:0; }}
  li {{ padding:.4rem 0; border-bottom:1px solid #1f2937; }}
</style>
</head>
<body {attr_string(body)}>
<main>
  <h1>Payment desk</h1>
  <p class="muted">Quantity quantities live in durable store · agents share <code>@st.action</code> with buttons</p>
  {st.paint("status", wrap=False)}
  {st.paint("orders", wrap=False)}
  <div class="row">
    {demo_button(ch, "Select 1001", select_order, trust_order_id="ord_1001")}
    {demo_button(ch, "Pay", pay_order)}
    {demo_button(ch, "Refund", refund_order)}
    {demo_button(ch, "Reset", reset_demo)}
  </div>
</main>
</body></html>"""
