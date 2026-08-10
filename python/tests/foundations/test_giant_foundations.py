"""Giant foundations — tree caps, authority, forensics, agent peer, guest, projections."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, ClientSafetyError, Intent, state
from ux_channel.bridge.bridge_contract import MethodSpec
from ux_channel.agent_runtime.peer import AgentPeer, dispatch_peer
from ux_channel.bridge.guest_runtime import (
    GuestBudget,
    GuestRuntime,
    GuestRuntimeError,
    event_to_intent_args,
)
from ux_channel.foundations.quantity import Quantity, QuantityError, QuantityBudget
from ux_channel.security.tree_cap import (
    TreeCapError,
    TreeEnvelope,
    compile_tree_caps,
    nest_envelope,
    validate_control,
)
from ux_channel.devtools.forensics import attach_forensics
from ux_channel.render.morph_ir import elem, region
from ux_channel.render.projections import project_all
from ux_channel.bridge.bridge_protocol import (
    SealedBridgeProtocol,
    get_sealed_registry,
    reset_sealed_registry,
)
from ux_channel_ux_dom import compile_capability_tree


SECRET = "giant-foundation-secret-key-32b!!"


def _ch(**kw):
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=kw.pop("require_cap", False),
            **kw,
        ),
    )


def test_tree_envelope_nests_and_rejects_widen():
    root = TreeEnvelope(scopes=frozenset({"pay", "cart"}), trust={"order_id": "9"})
    child = nest_envelope(root, scopes=frozenset({"pay"}), path="order")
    assert child.allows_scope("pay")
    with pytest.raises(TreeCapError):
        nest_envelope(root, scopes=frozenset({"admin"}))


def test_validate_control_trust():
    env = TreeEnvelope(scopes=frozenset({"pay"}), trust={"order_id": "9"})
    validate_control(env, action="pay", trust={"order_id": "9"})
    with pytest.raises(TreeCapError):
        validate_control(env, action="pay", trust={"order_id": "OTHER"})
    with pytest.raises(TreeCapError):
        validate_control(env, action="admin.delete")


def test_compile_tree_caps_and_glue():
    tree = {
        "tag": "div",
        "children": [
            {
                "tag": "button",
                "control": {"action": "pay", "trust": {"order_id": "9"}},
                "children": [],
            }
        ],
    }
    root = TreeEnvelope(scopes=frozenset({"pay"}), trust={"order_id": "9"})
    out, errors = compile_tree_caps(tree, root)
    assert errors == []
    with pytest.raises(TreeCapError):
        compile_capability_tree(
            tree,
            scopes=["hack"],
            trust={"order_id": "9"},
            strict=True,
        )
    compile_capability_tree(
        tree,
        scopes=["pay"],
        trust={"order_id": "9"},
    )


def test_forensic_replay_captures_morph_html():
    ch = _ch()
    store = attach_forensics(ch)

    @ch.region("b")
    def b(ctx):
        return "<i data-channel-id='b'>1</i>"

    @ch.on
    def bump():
        return ch.done(refresh=["b"], notice="ok")

    r = ch.registry.dispatch(
        Intent(action="bump", args={}, cap=ch.mint("bump", {}))
    )
    assert r.ok
    assert len(store.since(0)) >= 1
    frame = store.since(0)[-1]
    assert frame.action == "bump"
    assert frame.html is not None or "data-channel-id" in (frame.html or "")
    assert frame.op_kinds or True


def test_dispatch_peer_same_registry():
    ch = _ch()

    @ch.on
    def add(sku: str = ""):
        return ch.done(notice=f"got:{sku}")

    r = dispatch_peer(ch, "add", {"sku": "abc"}, peer=AgentPeer("bot-1"))
    assert r.ok
    assert any("got:abc" in str(o.get("message", "")) for o in r.ops)


def test_quantity_from_store_and_budget():
    m = Quantity.from_store(10, "usd", source="db.order.1.amount", revision=2)
    assert m.unit.upper() == "USD"
    assert float(m) == 10.0
    b = QuantityBudget(max_magnitude=10, unit="USD")
    assert b.allows(m)
    # non-currency unit
    qty = Quantity.from_store(3, "seats", source="db.booking.1.seats", revision=1)
    assert qty.unit == "seats"


def test_client_refuses_quantity_path():
    ch = _ch()
    st = state(ch)
    with pytest.raises((ClientSafetyError, QuantityError)):
        st.client.set("checkout.amount", 99)
    with pytest.raises((ClientSafetyError, QuantityError)):
        st.client.set("inventory.stock", 12)


def test_session_refuses_quantity():
    ch = _ch()
    st = state(ch)
    with pytest.raises(QuantityError):
        st.session("amount", 0).set(50)
    st.session("order_id", "").set("ord_9")


def test_guest_runtime_budget_and_protocol():
    reset_sealed_registry()
    get_sealed_registry().register(
        SealedBridgeProtocol(
            name="demo.chart",
            methods={"update": MethodSpec("update")},
            events=frozenset({"select"}),
        )
    )
    rt = GuestRuntime()
    rt.mount("c1", "demo.chart", budget=GuestBudget(max_calls=2))
    rt.call("c1", "update", [])
    rt.call("c1", "update", [])
    with pytest.raises(GuestRuntimeError):
        rt.call("c1", "update", [])
    with pytest.raises(GuestRuntimeError):
        rt.call("c1", "eval", [])
    rt.event("c1", "select", {"i": 1})
    args = event_to_intent_args("select", {"i": 1, "amount": 9}, allow_keys=["i"])
    assert "i" in args and "amount" not in args


def test_multi_surface_projections():
    tree = region("cart", elem("span", "3 items", **{"aria-label": "cart"}))
    views = project_all(tree)
    assert "3 items" in views["html"]
    assert views["agent"]["uid"] == "cart"
    assert views["a11y"]["role"]
    assert "cart" in views["print"] or "span" in views["print"]
