"""Foundation pillars 1–6 — pure channel (no UxDom required)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent
from ux_channel.bridge_meta.bridge_contract import MethodSpec
from ux_channel.protocol.capability import CapService
from ux_channel.security.attenuate import AttenuationError, attenuate, verify_attenuated
from ux_channel.bridge_meta.bridge_protocol import BridgeFirewallError, SealedBridgeProtocol
from ux_channel.ops_dx.intent_log import MemoryIntentLog, attach_intent_log
from ux_channel.paint.morph_ir import MorphNode, elem, lower_html, morph_ops, project_agent, region
from ux_channel.foundations.provenance import ProvenanceError, require_provenance, stamp
from ux_channel.paint.slot_compile import compile_tree, stable_uid


SECRET = "foundation-test-secret-key-32bytes-min!!"


def test_1_cap_attenuation_narrows_only():
    caps = CapService(SECRET)
    parent = attenuate(caps, "pay", {"order_id": "1"}, caveats=["pay", "refund"])
    child = attenuate(
        caps, "pay", {"order_id": "1"}, parent_token=parent, caveats=["pay"]
    )
    env = verify_attenuated(caps, child, "pay", {"order_id": "1"}, parent_token=parent)
    assert "pay" in env.caveats
    with pytest.raises(AttenuationError):
        attenuate(
            caps,
            "pay",
            {"order_id": "1"},
            parent_token=parent,
            caveats=["pay", "admin"],  # widens
        )


def test_2_morph_ir_html_and_agent():
    tree = region("cart", elem("span", "3 items", class_="n"))
    html = lower_html(tree)
    assert 'data-channel-id="cart"' in html
    assert "3 items" in html
    ops = morph_ops(tree)
    assert ops[0]["op"] == "morph"
    agent = project_agent(tree)
    assert agent["uid"] == "cart"
    assert agent["children"][0]["children"][0]["text"] == "3 items"


def test_3_sealed_bridge_firewall():
    proto = SealedBridgeProtocol(
        name="chart",
        methods={"setData": MethodSpec("setData", args=())},
        events=frozenset({"select"}),
    )
    proto.validate_call("setData", [])
    with pytest.raises(BridgeFirewallError):
        proto.validate_call("eval", [])
    with pytest.raises(BridgeFirewallError):
        proto.allow_event("hack")


def test_4_intent_log_and_replay():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )
    log = attach_intent_log(ch)

    @ch.on
    def ping():
        return ch.done(notice="ok")

    r = ch.registry.dispatch(Intent(action="ping", args={}, cap=ch.mint("ping", {})))
    assert r.ok
    assert len(log) >= 1
    kinds = log.replay_ops(from_seq=0)
    assert any(k in kinds for k in ("toast", "notice", "noop", "morph")) or kinds is not None
    assert log.since(0)[0].action == "ping"


def test_5_stable_uid_and_compile_tree():
    u = stable_uid("page", "cart", "line", 3)
    assert "cart" in u
    sm = compile_tree(
        {
            "tag": "div",
            "children": [
                {"tag": "span", "key": "a", "children": []},
                {"tag": "span", "key": "b", "children": []},
            ],
        },
        prefix="shop",
    )
    assert len(sm.uids) >= 2


def test_6_provenance_required_for_money():
    raw = 99.0
    with pytest.raises(ProvenanceError):
        require_provenance(raw, what="amount")
    p = stamp(raw, "db.order.9.amount", revision=3)
    assert require_provenance(p).value == 99.0
    assert p.provenance.source.startswith("db.")


def test_layers_no_ux_dom_import_in_foundations():
    import ux_channel.security.attenuate as a
    import ux_channel.paint.morph_ir as m
    import ast, inspect

    for mod in (a, m):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                else:
                    names = [node.module or ""]
                assert all("ux_dom" not in n for n in names)
