"""Architecture invariants — Hypothesis. Cap still authorizes; flow is not a cap."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from ux_channel.arch import (
    HostConfig,
    HostRuntime,
    PeerApply,
    ProofService,
    graph,
    make_web_drivers,
    project,
    seq,
    toast,
)
from ux_channel.arch.effects import after, invoke, morph, navigate
from ux_channel.arch.modes import validate_arch_modes
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.protocol.capability import CapError, CapService

settings.register_profile(
    "arch_props",
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("arch_props")

_msg = st.text(min_size=1, max_size=24)
_sid = st.from_regex(r"[a-z][a-z0-9_]{0,10}", fullmatch=True)


def _ops_kinds(ops) -> set[str]:
    kinds: set[str] = set()

    def walk(lst):
        for op in lst or []:
            if isinstance(op, dict):
                if op.get("op"):
                    kinds.add(str(op["op"]))
                walk(op.get("ops"))

    walk(ops)
    return kinds


@given(msg=_msg)
def test_project_classic_never_emits_seq(msg):
    g = graph(seq(toast(msg), toast(msg + "!")))
    ops = project(g, {"profiles": ["web.v1"], "features": ["seq"]}, effects="classic")
    assert "seq" not in _ops_kinds(ops)
    assert "toast" in _ops_kinds(ops)


@given(msg=_msg)
def test_project_empty_hello_is_classic_floor(msg):
    g = graph(seq(toast(msg)))
    ops = project(g, {}, effects="auto")
    assert "seq" not in _ops_kinds(ops)


@given(msg=_msg)
def test_project_auto_web_keeps_seq(msg):
    g = graph(seq(toast(msg)))
    ops = project(g, {"profiles": ["web.v1"], "features": ["seq"]}, effects="auto")
    assert ops and ops[0]["op"] == "seq"


@given(msg=_msg)
def test_agent_only_drops_morph_keeps_toast(msg):
    g = graph(morph("#x", "<b>hi</b>"), toast(msg), navigate("/go"))
    ops = project(g, {"profiles": ["agent.v1"]}, effects="auto")
    kinds = _ops_kinds(ops)
    assert "morph" not in kinds
    assert "navigate" not in kinds
    assert "toast" in kinds


@given(sid=_sid, gen=st.integers(min_value=1, max_value=50), msg=_msg)
def test_proof_roundtrip_and_tamper(sid, gen, msg):
    p = ProofService("proof-secret-16b!")
    result = {"ok": True, "ops": [{"op": "toast", "message": msg}]}
    p.sign(result, session_id=sid, gen=gen)
    assert p.verify(result, session_id=sid, gen=gen)
    result["ops"] = [{"op": "toast", "message": msg + "x"}]
    assert p.verify(result, session_id=sid, gen=gen) is False


@given(sid=_sid, gen=st.integers(min_value=1, max_value=50))
def test_proof_wrong_session_or_gen_fails(sid, gen):
    p = ProofService("proof-secret-16b!")
    result = {"ok": True, "ops": [{"op": "toast", "message": "ok"}]}
    p.sign(result, session_id=sid, gen=gen)
    assert p.verify(result, session_id=sid + "z", gen=gen) is False
    assert p.verify(result, session_id=sid, gen=gen + 1) is False


@given(n=st.integers(min_value=1, max_value=20))
def test_apply_budget_rejects_over_limit(n):
    peer = PeerApply(make_web_drivers(), max_nodes=n)
    ops = [{"op": "toast", "message": str(i)} for i in range(n + 1)]
    peer.apply_result({"ok": True, "ops": ops})
    assert peer.ctx["reject"] == "budget"
    assert peer.ctx["log"] == []


@given(msg=_msg, flow=st.from_regex(r"flow_[a-z0-9]{1,8}", fullmatch=True))
def test_flow_id_never_blocks_apply(msg, flow):
    peer = PeerApply(make_web_drivers())
    peer.apply_result(
        {
            "ok": True,
            "ops": [{"op": "toast", "message": msg}],
            "meta": {"flow_id": flow, "not_a_cap": True},
        }
    )
    assert any(x[0] == "toast" for x in peer.ctx["log"])


@given(action=st.from_regex(r"[A-Z][A-Za-z]{2,8}\.[a-z]{2,8}", fullmatch=True))
def test_once_then_replay_fails(action):
    store = MemoryNonceStore()
    caps = CapService("0123456789abcdef", nonce_store=store)
    tok = caps.mint(action, {}, once=True)
    caps.verify(tok, action, {})
    with pytest.raises(CapError):
        caps.verify(tok, action, {})


@given(rid=st.from_regex(r"r[a-z0-9]{1,8}", fullmatch=True))
def test_request_id_dedupes_without_being_once(rid):
    hits = {"n": 0}
    host = HostRuntime(
        cap_secret="0123456789abcdef",
        proof_secret="proof-secret-16b!",
        config=HostConfig(demo_mode=True, require_cap=False, proofs="off"),
    )

    def ping(args, ctx):
        hits["n"] += 1
        return {"ok": True, "ops": [{"op": "toast", "message": "x"}]}

    host.register("Open.ping", ping)
    host.handle_intent({"action": "Open.ping", "args": {}, "request_id": rid})
    host.handle_intent({"action": "Open.ping", "args": {}, "request_id": rid})
    assert hits["n"] == 1


def test_modes_reject_unknown():
    with pytest.raises(ValueError):
        validate_arch_modes("rich", "auto", "auto")
    with pytest.raises(ValueError):
        validate_arch_modes("auto", "maybe", "auto")
    with pytest.raises(ValueError):
        validate_arch_modes("auto", "auto", "yes")


def test_project_unknown_effects_raises():
    with pytest.raises(ValueError):
        project(graph(toast("x")), {}, effects="rich")


def test_after_classic_drops_future_timer():
    ops = project(graph(after(50, toast("later"))), {}, effects="classic")
    assert ops == []
    ops0 = project(graph(after(0, toast("now"))), {}, effects="classic")
    assert ops0 and ops0[0]["op"] == "toast"


def test_invoke_classic_inlines_body():
    g = graph(invoke("st1", "ping", body=[toast("hi")]))
    ops = project(g, {}, effects="classic")
    assert ops == [{"op": "toast", "message": "hi", "level": "info"}]


def test_coverage_builders_stamps_flow_and_attach():
    from ux_channel import Channel
    from ux_channel.arch import (
        FlowStore,
        StampTable,
        after,
        attach_flow_meta,
        dispatch_event,
        make_agent_drivers,
        make_trace_drivers,
        make_wire_drivers,
        morph,
        navigate,
        new_flow_id,
    )
    from ux_channel.arch.effects import invoke as inv
    from ux_channel.arch.flow_store import FlowError

    g = graph(
        morph("#t", "<b>x</b>"),
        navigate("/go", replace=True),
        dispatch_event("ping", target="#t", detail={"a": 1}),
        after(0, toast("now"), timer_id="t0"),
        inv("s", "m", args={"k": 1}),
        toast("d", duration_ms=10),
    )
    ops = project(g, {"profiles": ["web.v1"], "features": ["seq"]}, effects="auto")
    kinds = _ops_kinds(ops)
    assert "morph" in kinds and "navigate" in kinds and "dispatch" in kinds

    st = StampTable()
    sid = st.grant("s", 1, "island", {"ping"}).stamp_id
    assert st.allows("s", sid, 1, "ping")
    assert not st.allows("s", sid, 2, "ping")
    assert not st.allows("s", "nope", 1, "ping")
    st.on_revoke("s")
    assert not st.allows("s", sid, 1, "ping")

    fs = FlowStore()
    rec = fs.start("wizard")
    fid = rec.flow_id
    fs.advance(fid, data={"k": 1})
    fs.complete(fid)
    with pytest.raises(FlowError):
        fs.complete("missing")
    with pytest.raises(FlowError):
        fs.advance(fid)
    result = {"ok": True, "ops": [], "meta": {}}
    attach_flow_meta(result, flow_id=fid, flow_mode="auto")
    assert result["meta"]["flow_id"] == fid

    make_web_drivers()
    make_agent_drivers()
    make_trace_drivers()
    make_wire_drivers()

    ch = Channel.boot(secret="dev-secret-key-32chars-minimum!!!!")
    ch.set_hello("s1", {"profiles": ["web.v1"], "features": ["seq"], "effect_proof": True})
    r = ch.emit_graph(graph(toast("hi")), session_id="s1")
    assert r.ok
    ch.grant_stamp("s1", "island", {"ping"})
    ch.revoke_session("s1")

