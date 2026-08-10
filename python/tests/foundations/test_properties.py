"""
Property-based tests (Hypothesis) for uxchannel control-plane invariants.

  pytest tests/test_properties.py -q
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest
from fastapi import FastAPI
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from ux_channel import Channel, ChannelConfig, agents, state
from ux_channel.capability import CapService, CapError
from ux_channel.quantity import (
    Quantity,
    QuantityError,
    refuse_client_quantity,
    refuse_session_quantity,
)
from ux_channel.tree_cap import TreeEnvelope, nest_envelope, validate_control, TreeCapError
from ux_channel.slot_compile import stable_uid
from ux_channel.attenuate import attenuate, verify_attenuated, AttenuationError
from ux_channel.planes import path_is_risky as planes_risky


SECRET = "hypothesis-ux-channel-secret-key!!"
settings.register_profile(
    "ux_channel",
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.load_profile("ux_channel")


safe_seg = st.from_regex(r"[a-z][a-z0-9_]{0,12}", fullmatch=True)
authority_seg = st.sampled_from(
    [
        "amount",
        "price",
        "total",
        "balance",
        "payment",
        "pay",
        "token",
        "password",
        "secret",
        "quota",
        "inventory",
        "dosage",
        "score",
    ]
)
amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
units = st.sampled_from(["USD", "EUR", "kg", "seats", "mg", "credits"])
action_name = st.from_regex(r"[a-z][a-z0-9_]{0,16}", fullmatch=True)
order_id = st.from_regex(r"ord_[a-z0-9]{1,8}", fullmatch=True)


def _ch(**kw):
    app = FastAPI()
    cfg_kw = {
        "secret": SECRET,
        "allow_memory_stores": True,
        "require_cap": kw.pop("require_cap", False),
        **kw,
    }
    return Channel.boot(app, config=ChannelConfig.development(**cfg_kw))


@given(seg=authority_seg, prefix=safe_seg, suffix=safe_seg)
def test_prop_risky_segments_always_flagged(seg, prefix, suffix):
    path = f"{prefix}.{seg}.{suffix}"
    assert planes_risky(path) is True


@given(seg=safe_seg)
def test_prop_benign_single_segment_not_authority_token(seg):
    assume(
        seg
        not in {
            "amount",
            "price",
            "total",
            "balance",
            "payment",
            "pay",
            "charge",
            "cart",
            "order",
            "checkout",
            "card",
            "cvv",
            "cvc",
            "pan",
            "password",
            "passwd",
            "secret",
            "token",
            "cap",
            "quota",
            "inventory",
            "dosage",
            "score",
            "stock",
            "credits",
            "limit",
            "capacity",
        }
    )
    if seg == "payload":
        assert planes_risky(seg) is False


@given(value=amounts, unit=units, revision=st.integers(1, 1000))
def test_prop_quantity_roundtrip_dict(value, unit, revision):
    m = Quantity.from_store(value, unit, source="db.record.x.value", revision=revision)
    d = m.to_dict()
    assert d["magnitude"] == str(value) or Decimal(d["magnitude"]) == value
    assert d["unit"] == unit
    assert d["provenance"]["revision"] == revision
    assert d["provenance"]["source"].startswith("db.")


@given(value=amounts)
def test_prop_session_refuses_numeric_under_quantity_key(value):
    with pytest.raises(QuantityError):
        refuse_session_quantity("amount", value)
    with pytest.raises(QuantityError):
        refuse_session_quantity("checkout.price", float(value))
    with pytest.raises(QuantityError):
        refuse_session_quantity("inventory.quota", float(value))


@given(
    path=st.sampled_from(
        ["amount", "checkout.amount", "pay.total", "access_token", "inventory.stock"]
    )
)
def test_prop_client_refuses_risky_paths(path):
    with pytest.raises(Exception):
        refuse_client_quantity(path, 1)


@given(oid=order_id)
def test_prop_cap_sign_verify_roundtrip(oid):
    caps = CapService(SECRET)
    tok = attenuate(caps, "pay", {"order_id": oid}, caveats=["pay"])
    env = verify_attenuated(caps, tok, "pay", {"order_id": oid})
    assert env.action == "pay"
    assert env.args_hash


@given(oid=order_id)
def test_prop_cap_args_mismatch_detected(oid):
    caps = CapService(SECRET)
    tok = attenuate(caps, "pay", {"order_id": oid}, caveats=["pay"])
    with pytest.raises(CapError):
        verify_attenuated(caps, tok, "pay", {"order_id": "x"})


@given(
    narrow=st.lists(
        st.sampled_from(["pay", "refund", "cart"]), min_size=1, max_size=2, unique=True
    ),
    extra=st.sampled_from(["admin", "super", "root"]),
)
def test_prop_attenuation_rejects_widen(narrow, extra):
    assume(extra not in narrow)
    caps = CapService(SECRET)
    parent = attenuate(
        caps, "pay", {"order_id": "ord_1"}, caveats=list(narrow)
    )
    with pytest.raises(AttenuationError):
        attenuate(
            caps,
            "pay",
            {"order_id": "ord_1"},
            parent_token=parent,
            caveats=list(narrow) + [extra],
        )


@given(
    scopes=st.lists(
        st.sampled_from(["pay", "cart", "refund"]), min_size=1, max_size=3, unique=True
    ),
    foreign=action_name,
)
def test_prop_envelope_rejects_foreign_action(scopes, foreign):
    assume(foreign not in scopes and not any(foreign.startswith(s) for s in scopes))
    env = TreeEnvelope(scopes=frozenset(scopes), trust={"order_id": "1"})
    with pytest.raises(TreeCapError):
        validate_control(env, action=foreign, trust={"order_id": "1"})


@given(oid=order_id, other=order_id)
def test_prop_envelope_trust_must_match(oid, other):
    assume(oid != other)
    env = TreeEnvelope(scopes=frozenset({"pay"}), trust={"order_id": oid})
    validate_control(env, action="pay", trust={"order_id": oid})
    with pytest.raises(TreeCapError):
        validate_control(env, action="pay", trust={"order_id": other})


@given(
    parent_scopes=st.lists(
        st.sampled_from(["pay", "cart", "refund", "view"]),
        min_size=2,
        max_size=4,
        unique=True,
    ),
    data=st.data(),
)
def test_prop_nest_envelope_scopes_subset(parent_scopes, data):
    child_scopes = data.draw(
        st.lists(
            st.sampled_from(parent_scopes),
            min_size=1,
            max_size=len(parent_scopes),
            unique=True,
        )
    )
    root = TreeEnvelope(scopes=frozenset(parent_scopes), trust={})
    child = nest_envelope(root, scopes=frozenset(child_scopes), path="c")
    assert child.scopes.issubset(root.scopes)


@given(
    parts=st.lists(
        st.from_regex(r"[A-Za-z][A-Za-z0-9_]{0,8}", fullmatch=True),
        min_size=1,
        max_size=5,
    )
)
def test_prop_stable_uid_deterministic(parts):
    assume(all(p.strip() for p in parts))
    a = stable_uid(*parts)
    b = stable_uid(*parts)
    assert a == b
    assert re.match(r"^[A-Za-z0-9_.:@+-]+$", a)


@given(junk=st.sampled_from(["-", "--", "---"]))
def test_prop_stable_uid_rejects_empty_after_sanitize(junk):
    with pytest.raises(ValueError):
        stable_uid(junk)


@given(n=st.integers(1, 5))
def test_prop_tools_for_subset_of_registry(n):
    ch = _ch()
    ag = agents(ch)
    for i in range(n):

        def _mk(i=i):
            @ch.on(name=f"act_{i}")
            def _fn():
                return ch.done()

        _mk()
    tools = ag.tools_for()
    tool_names = {t["name"] for t in tools}
    assert set(tool_names) <= set(ch.registry.names())
    json.dumps(tools)


def test_prop_situation_exclude_not_in_allowed():
    ch = _ch()
    ag = agents(ch)

    @ch.on
    def pay_order():
        return ch.done()

    @ch.on
    def refund_order():
        return ch.done()

    @ch.on
    def reset_demo():
        return ch.done()

    @ch.on
    def select_order():
        return ch.done()

    sit = ag.situation(facts={"x": 1}, exclude=["refund_order"])
    assert "refund_order" not in sit["allowed"]
    assert sit["facts"] == {"x": 1}
    assert set(sit.keys()) >= {
        "tool_count",
        "facts",
        "principal",
        "blocked",
        "notices",
        "allowed",
    }
    json.dumps(sit, default=str)


def test_prop_effects_ok_matches_result_ok():
    ch = _ch()
    ag = agents(ch)
    st_ = state(ch)
    n = st_.session("n", 0)

    @ch.on
    def inc():
        n.add(1)
        return ch.done()

    @ch.on
    def boom():
        return ch.fail.validation("nope")

    for action in ("inc", "boom"):
        r = ag.dispatch(action, {})
        fx = ag.effects(r)
        assert fx.ok is r.ok
        if r.ok:
            assert fx.error_code is None
        else:
            assert fx.error_code is not None


def test_prop_payment_status_machine():
    ch = _ch()
    ag = agents(ch)
    st_ = state(ch)
    orders = {
        "ord_1": {"status": "open", "revision": 1, "amount": Decimal("10.00")},
        "ord_2": {"status": "open", "revision": 1, "amount": Decimal("20.00")},
    }
    selected = st_.session("order_id", "")

    @ch.on
    def select_order(order_id: str = "ord_1"):
        selected.set(order_id)
        return ch.done()

    @ch.on
    def pay_order(order_id: str = ""):
        oid = order_id or selected.peek()
        o = orders[oid]
        if o["status"] != "open":
            return ch.fail.validation(f"order is {o['status']}")
        o["status"] = "paid"
        return ch.done()

    @ch.on
    def refund_order(order_id: str = ""):
        oid = order_id or selected.peek()
        o = orders[oid]
        if o["status"] != "paid":
            return ch.fail.validation("only paid")
        o["status"] = "refunded"
        return ch.done()

    @ch.on
    def reset_demo():
        for o in orders.values():
            o["status"] = "open"
        return ch.done()

    ag.dispatch("select_order", {"order_id": "ord_1"})
    r = ag.dispatch("pay_order", {})
    assert r.ok
    assert orders["ord_1"]["status"] == "paid"
    before = orders["ord_1"]["status"]
    r2 = ag.dispatch("pay_order", {})
    assert not r2.ok
    assert orders["ord_1"]["status"] == before
    r3 = ag.dispatch("refund_order", {})
    assert r3.ok
    assert orders["ord_1"]["status"] == "refunded"
    ag.dispatch("reset_demo", {})
    assert orders["ord_1"]["status"] == "open"


def test_prop_agent_dispatch_cap_with_args_under_require_cap():
    ch = _ch(require_cap=True)
    ag = agents(ch)

    @ch.on
    def select_order(order_id: str = "ord_1"):
        return ch.done(notice=order_id)

    r = ag.dispatch(
        "select_order",
        {"order_id": "ord_1"},
        peer=ag.peer("bot-4"),
    )
    assert r.ok
