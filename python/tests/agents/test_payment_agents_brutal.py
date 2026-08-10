"""
Brutal stability suite: payment plane + multi-agent situation + money + audit.

Run: pytest tests/test_payment_agents_brutal.py tests/test_agents_reality.py -q
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import threading
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI

from ux_channel import (
    Channel,
    ChannelConfig,
    ClientSafetyError,
    Intent,
    agents,
    attach_audit,
    state,
)
from ux_channel.context import Principal
from ux_channel.quantity import Quantity, QuantityError


SECRET = "brutal-pay-agents-secret-key-32b!!!"


def _boot(*, audit: bool = True, require_cap: bool = False) -> Channel:
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=require_cap,
            audit=audit,
        ),
    )


def _payment_world(ch: Channel):
    """Minimal payment domain on a fresh channel (mirrors example app)."""
    st = state(ch)
    ag = agents(ch)
    orders: dict[str, dict[str, Any]] = {
        "ord_1": {
            "user_id": "alice",
            "amount": Decimal("42.00"),
            "currency": "USD",
            "status": "open",
            "revision": 1,
        },
        "ord_2": {
            "user_id": "bob",
            "amount": Decimal("15.50"),
            "currency": "USD",
            "status": "open",
            "revision": 1,
        },
    }

    def load_authority(oid: str) -> Quantity:
        o = orders[oid]
        return Quantity.from_store(
            o["amount"], o["currency"], source=f"db.order.{oid}.amount", revision=o["revision"]
        )

    def facts() -> dict:
        return {
            "orders": {
                oid: {
                    "user_id": o["user_id"],
                    "status": o["status"],
                    "payable": load_authority(oid).to_dict(),
                }
                for oid, o in orders.items()
            },
            "selected_order": st.session("selected_order", "").peek() or None,
            "pay_step": st.session("pay_step", "review").peek(),
        }

    @ch.on
    def select_order(order_id: str = "ord_1"):
        if order_id not in orders:
            return ch.fail.validation("unknown")
        st.session("selected_order", "").set(order_id)
        st.session("pay_step", "review").set("confirm")
        return ch.done(notice=f"selected {order_id}")

    @ch.on
    def pay_order(order_id: str = ""):
        oid = order_id or st.session("selected_order", "").peek() or ""
        if oid not in orders:
            return ch.fail.validation("need order")
        o = orders[oid]
        if o["status"] != "open":
            return ch.fail.validation(f"status {o['status']}")
        st.db.guard({"order_id": oid})
        money = load_authority(oid)
        st.db.require(amount=float(money.magnitude))
        o["status"] = "paid"
        o["revision"] += 1
        st.session("pay_step", "review").set("done")
        return ch.done(notice=f"paid {money.magnitude}")

    @ch.on
    def refund_order(order_id: str = ""):
        oid = order_id or st.session("selected_order", "").peek() or ""
        if oid not in orders:
            return ch.fail.validation("need order")
        o = orders[oid]
        if o["status"] != "paid":
            return ch.fail.validation("not paid")
        o["status"] = "refunded"
        o["revision"] += 1
        return ch.done(notice=f"refunded {oid}")

    @ch.on
    def reset_demo():
        for o in orders.values():
            o["status"] = "open"
            o["revision"] = 1
        st.session("selected_order", "").set("")
        st.session("pay_step", "review").set("review")
        return ch.done(notice="reset")

    return st, ag, orders, facts, load_authority


# ── Core multi-agent payment ─────────────────────────────────────────────


def test_full_payment_flow_three_agents_situation_shape():
    ch = _boot()
    st, ag, orders, facts, _ = _payment_world(ch)

    sit0 = ag.situation(
        Principal(id="agent.clerk"),
        facts=facts(),
        notices=["clerk"],
        exclude=["refund_order", "reset_demo"],
    )
    assert sit0["principal"] == "agent.clerk"
    assert "select_order" in sit0["allowed"]
    assert "refund_order" not in sit0["allowed"]
    assert sit0["facts"]["orders"]["ord_1"]["payable"]["magnitude"] == "42.00"
    assert sit0["facts"]["orders"]["ord_1"]["payable"]["provenance"]["source"].startswith(
        "db.order."
    )

    r1 = ag.dispatch("select_order", {"order_id": "ord_1"}, peer=ag.peer("agent.clerk"))
    assert r1.ok
    fx1 = ag.effects(r1)
    assert fx1.ok
    assert any("selected" in n for n in fx1.notices)

    sit1 = ag.situation(Principal(id="agent.cashier"), facts=facts())
    assert sit1["facts"]["selected_order"] == "ord_1"
    assert sit1["facts"]["pay_step"] == "confirm"

    r2 = ag.dispatch("pay_order", {"order_id": "ord_1"}, peer=ag.peer("agent.cashier"))
    assert r2.ok
    assert orders["ord_1"]["status"] == "paid"
    assert orders["ord_1"]["revision"] == 2

    sit2 = ag.situation(Principal(id="agent.refund"), facts=facts(), include=["refund_order"])
    assert sit2["facts"]["orders"]["ord_1"]["status"] == "paid"
    assert sit2["allowed"] == ["refund_order"]

    r3 = ag.dispatch("refund_order", {"order_id": "ord_1"}, peer=ag.peer("agent.refund"))
    assert r3.ok
    assert orders["ord_1"]["status"] == "refunded"

    sit3 = ag.situation(Principal(id="agent.auditor"), facts=facts(), include=[])
    assert sit3["allowed"] == []
    assert sit3["facts"]["orders"]["ord_1"]["payable"]["provenance"]["revision"] == 3


def test_human_intent_and_agent_dispatch_identical_mutation():
    ch = _boot()
    st, ag, orders, facts, _ = _payment_world(ch)

    r_h = ch.registry.dispatch(
        Intent(action="select_order", args={"order_id": "ord_2"}, cap=ch.mint("select_order", {"order_id": "ord_2"}))
    )
    assert r_h.ok
    assert st.session("selected_order", "").peek() == "ord_2"

    # agent pays same order
    r_a = ag.dispatch("pay_order", {"order_id": "ord_2"}, peer=ag.peer("bot"))
    assert r_a.ok
    assert orders["ord_2"]["status"] == "paid"


def test_block_unblock_policy_stable():
    ch = _boot()
    _, ag, _, _, _ = _payment_world(ch)
    ag.block("refund_order", "reset_demo")
    r = ag.dispatch("refund_order", {"order_id": "ord_1"})
    assert not r.ok
    assert r.error.code == "forbidden" or "forbidden" in str(r.error).lower()
    fx = ag.effects(r)
    assert fx.action == "refund_order"
    assert not fx.ok

    sit = ag.situation(facts={})
    assert "refund_order" in sit["blocked"]

    ag.unblock("refund_order")
    # still not paid — validation fail not forbidden
    r2 = ag.dispatch("refund_order", {"order_id": "ord_1"})
    assert not r2.ok  # not paid


def test_money_invariants_client_and_session():
    ch = _boot()
    st, _, _, _, _ = _payment_world(ch)
    with pytest.raises((ClientSafetyError, QuantityError)):
        st.client.set("payment.amount", 99)
    with pytest.raises(QuantityError):
        st.session("amount", 0).set(50)
    # id chrome ok
    st.session("order_id", "").set("ord_1")
    assert st.session("order_id", "").peek() == "ord_1"


def test_pay_never_uses_client_amount_path():
    """pay_order only loads Quantity from orders dict — client signal cannot change amount."""
    ch = _boot()
    st, ag, orders, _, load_authority = _payment_world(ch)
    # even if something tried to set a number under a non-risky key, pay uses DB
    st.session("selected_order", "").set("ord_1")
    orders["ord_1"]["amount"] = Decimal("99.00")
    r = ag.dispatch("pay_order", {"order_id": "ord_1"})
    assert r.ok
    # notice contains 99.00 from DB not a forged client value
    fx = ag.effects(r)
    assert any("99" in n for n in fx.notices)


def test_double_pay_rejected():
    ch = _boot()
    _, ag, orders, _, _ = _payment_world(ch)
    assert ag.dispatch("pay_order", {"order_id": "ord_1"}).ok
    r2 = ag.dispatch("pay_order", {"order_id": "ord_1"})
    assert not r2.ok
    assert orders["ord_1"]["status"] == "paid"


def test_tools_for_stable_and_json_serializable():
    ch = _boot()
    _, ag, _, _, _ = _payment_world(ch)
    tools = ag.tools_for()
    names = {t["name"] for t in tools}
    assert {"select_order", "pay_order", "refund_order", "reset_demo"} <= names
    for t in tools:
        json.dumps(t)  # must serialize
        assert "parameters" in t
        assert "name" in t
    # exclude
    t2 = ag.tools_for(exclude=["reset_demo"])
    assert "reset_demo" not in [x["name"] for x in t2]


def test_situation_json_stable_keys():
    ch = _boot()
    _, ag, _, facts, _ = _payment_world(ch)
    sit = ag.situation(Principal(id="x"), facts=facts(), notices=["n"])
    for key in ("facts", "allowed", "blocked", "notices", "principal", "tool_count"):
        assert key in sit
    json.dumps(sit, default=str)


def test_audit_records_every_agent_dispatch():
    ch = _boot(audit=True)
    assert ch.audit is not None
    _, ag, _, _, _ = _payment_world(ch)
    ag.dispatch("select_order", {"order_id": "ord_1"})
    ag.dispatch("pay_order", {"order_id": "ord_1"})
    pack = ch.audit.export()
    actions = [i["action"] for i in pack["intents"]]
    assert "select_order" in actions
    assert "pay_order" in actions
    assert len(pack["frames"]) >= 2


def test_concurrent_agent_pays_different_orders():
    ch = _boot()
    _, ag, orders, _, _ = _payment_world(ch)
    lock = threading.Lock()
    errors = []

    def pay(oid: str):
        try:
            r = ag.dispatch("pay_order", {"order_id": oid}, peer=ag.peer(f"bot-{oid}"))
            with lock:
                if not r.ok:
                    errors.append((oid, r))
        except Exception as e:
            with lock:
                errors.append((oid, e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(pay, ["ord_1", "ord_2", "ord_1", "ord_2"]))
    # at least one success per order; second pay may fail
    assert orders["ord_1"]["status"] == "paid"
    assert orders["ord_2"]["status"] == "paid"


def test_chaos_random_agent_ops_no_crash():
    ch = _boot()
    _, ag, orders, facts, _ = _payment_world(ch)
    actions = [
        ("select_order", {"order_id": "ord_1"}),
        ("select_order", {"order_id": "ord_2"}),
        ("pay_order", {"order_id": "ord_1"}),
        ("pay_order", {"order_id": "ord_2"}),
        ("refund_order", {"order_id": "ord_1"}),
        ("refund_order", {"order_id": "ord_2"}),
        ("reset_demo", {}),
    ]
    rng = random.Random(42)
    for i in range(80):
        name, args = rng.choice(actions)
        if rng.random() < 0.1:
            ag.block("refund_order")
        if rng.random() < 0.1:
            ag.unblock("refund_order")
        r = ag.dispatch(name, args, peer=ag.peer(f"chaos-{i % 5}"))
        _ = ag.effects(r)
        sit = ag.situation(facts=facts(), exclude=["reset_demo"] if rng.random() < 0.3 else None)
        assert "facts" in sit
        json.dumps(sit, default=str)
    # world still consistent
    for o in orders.values():
        assert o["status"] in ("open", "paid", "refunded")
        assert o["revision"] >= 1


def test_require_cap_agent_dispatch_still_works():
    ch = _boot(require_cap=True)
    _, ag, _, _, _ = _payment_world(ch)
    # dispatch_peer signs caps when require_cap
    r = ag.dispatch("select_order", {"order_id": "ord_1"}, peer=ag.peer("capped-bot"))
    assert r.ok


def test_money_provenance_survives_pay_refund_cycle():
    ch = _boot()
    _, ag, orders, facts, load_authority = _payment_world(ch)
    m0 = load_authority("ord_1")
    assert m0.provenance.revision == 1
    ag.dispatch("pay_order", {"order_id": "ord_1"})
    m1 = load_authority("ord_1")
    assert m1.provenance.revision == 2
    ag.dispatch("refund_order", {"order_id": "ord_1"})
    m2 = load_authority("ord_1")
    assert m2.provenance.revision == 3
    sit = ag.situation(facts=facts())
    assert sit["facts"]["orders"]["ord_1"]["payable"]["provenance"]["revision"] == 3


def test_example_module_import_and_reset():
    """Import real example app and run one cycle (integration)."""
    import importlib
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    # fresh import of example
    if "examples.payment_agents.app" in sys.modules:
        del sys.modules["examples.payment_agents.app"]
    mod = importlib.import_module("examples.payment_agents.app")
    ag = mod.ag
    ag.clear_policy()
    r = ag.dispatch("reset_demo", {})
    assert r.ok
    sit = ag.situation(facts={
        "orders": {oid: {"status": o.status} for oid, o in mod.ORDERS.items()}
    })
    assert "allowed" in sit
    r2 = ag.dispatch("select_order", {"order_id": "ord_1001"})
    assert r2.ok
    r3 = ag.dispatch("pay_order", {"order_id": "ord_1001"})
    assert r3.ok
    assert mod.ORDERS["ord_1001"].status == "paid"
